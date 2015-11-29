

from boxsdk import OAuth2, Client
from dateutil import parser
import Constants
import csv
import requests
import json
import logging
import argparse as argParser

class Restore:

    """
    Restores a Box file system to a previous version.
    Requires a CSV containing all files to be rolled back.
    """

    # Simple logger
    logging.basicConfig(filename='script.log',level=logging.DEBUG)

    def __init__(self, shouldAuthenticate=False):
        """
        Initializes the Restore class.
        - Mainly provides OAuth2 authentication
        :return:
        """
        if shouldAuthenticate:
            self.oauth = OAuth2(Constants.CLIENT_ID,Constants.CLIENT_SECRET,self.store_tokens)
            self.auth_url, self.csrf_token = self.oauth.get_authorization_url('https://127.0.0.1')
            print(self.auth_url)
            auth_code = raw_input("Please enter auth_code after granting access: ")
            logging.info(auth_code)
            access_token, refresh_token = self.oauth.authenticate(auth_code)
            logging.info(access_token + " " + refresh_token)
            self.client = Client(self.oauth)


    def store_tokens(self, access_token, refresh_token):
        """
        We can leverage this token for accessing raw api calls
        :param access_token:
        :param refresh_token:
        :return:
        """
        self.access_token = access_token;
        self.authHeaders = {'Authorization' : ' Bearer ' + self.access_token}

    def printFilesStartingFromId(self, folder_id):
        """
        Printss all the files starting from the particular id ('0' is root)
	A simple debugging util.
        :param folder_id:
        :return:
        """

        # This is bad.. please don't use this function on large directories.
        # We could rewrite this to take chunks at a time, but this is really for
        # just ensuring that we can get access to all files from the root
        items = restore.client.folder(folder_id=folder_id).get_items(limit=10000000000000, offset=0)
        for item in items:
            if item._item_type == Constants.FOLDER:
                self.printFilesStartingFromId(item.object_id)
            logging.info( item['name'] )

    def findFilesWithNameContaining(self, filename):
        return self.client.search(query=filename, limit=100, offset=0)

    def rollbackFilesInCSV(self, csvFileName):
        """
        CSV format must be:
        Date / Time,
        User's Name,
        User's Email,
        IP Address,
        Action,
        Item / Name,
        Size,
        Contained in Folder
        Change Details
        :param csv:
        :return:
        """
        data = self._createDictFromCsvFile(csvFileName)
        filesCompleted = set()

        # For each file perform the roll back if necessary
        try:
            for filename, fileMetadata in data.iteritems():
                logging.info( "\n\nProcessing {}".format(filename))
                item = self._isRollbackRequired(filename, fileMetadata)
                if item is not None:
                    self.rollbackSingleFileOneVersion(item)
                    filesCompleted.add(item['parent']['name'] + '/' + item['name'])

            # Dumping files not completed
            self.dumpFilesNotCompleted(data, filesCompleted)
        except Exception as e:
            logging.info( "Error cannot finish processing files")
            logging.info( "Dumping remaining files to notCompletedFiles.txt")
            self.dumpFilesNotCompleted(data, filesCompleted)

    def dumpFilesNotCompleted(self, filesFromCSV, filesCompleted):
        """
        Dump all files that are not completed
        :param filesFromCSV:
        :param filesCompleted:
        :return:
        """
        with open("notCompletedFiles.txt", "w+") as f:
            for filename, fileMetadata in filesFromCSV.iteritems():
                key = fileMetadata['parent'] + '/' + filename
                if key not in filesCompleted:
                    f.write(key + '\n')


    def _getFileVersions(self, fileId):
        """
        Retrieves the versions of this file
        :param fileId:
        :return: the version data as a dictionary
        """
        versionsAPI = Constants.VERSIONS_API.replace('{id}', fileId)
        logging.info( 'Retrieving version data from api call: {}'.format(versionsAPI) )
        r = requests.get(versionsAPI, headers=self.authHeaders)
        versionData = json.loads(r.text)
        return versionData


    def _isRollbackRequired(self, filename, fileMetadata):
        """
        Determines if the roll back on the filename
        with meta data is required
        :param key:
        :param value:
        :return: True if the rollback is needed
        """
        # Search for file using client
        items = self.findFilesWithNameContaining(filename)
        logging.info( "Found {} items".format(len(items)) )
        # When there is more than 1 item we need to be sure
        # we grab the correct one
        actualItem = None
        if len(items) > 0:
            for item in items:
                if self._isCorrectFile(item, fileMetadata):
                    actualItem = item
                    break

        if actualItem is None:
            logging.info( "Rollback not required!" )
            return None;

        logging.info( "Found item {}".format(actualItem['name']) )

        return actualItem



    def _isCorrectFile(self, item, fileMetadata):
        """
        Check to see if the file is the correct version
        :param item:
        :param fileMetadata:
        :return: true if it is the correct file
        """

        logging.info( "Testing file found against parameters below" )
        logging.info( "\t" + item['name'] + " -> " + fileMetadata['name'] )
        logging.info( "\t" + item['modified_by']['name'] + " -> " + fileMetadata['modifiedBy'] )
        logging.info( "\t" + item['parent']['name'] + " -> " + fileMetadata['parent'] )
        if item['name'] == fileMetadata['name'] and \
                    item['modified_by']['name'] == fileMetadata['modifiedBy'] and \
                    item['parent']['name'] == fileMetadata['parent']:

            # Check if dates are equivalent
            itemDate = parser.parse(item['modified_at'])
            fileMetaDataDate = fileMetadata['modifiedAt']


            logging.info( "\t" + str(itemDate.date()) + " -> " + str(fileMetaDataDate.date()) )
            logging.info( "\t" + str(itemDate.time().hour) + " -> " + str(fileMetaDataDate.time().hour) )
            logging.info( "\t" + str(itemDate.time().minute) + " -> " + str(fileMetaDataDate.time().minute) )
            logging.info( 'Partially matched...' )

            if itemDate.date() == fileMetaDataDate.date():
                logging.info( 'Matched date' )
                if itemDate.time().hour == fileMetaDataDate.time().hour:
                    logging.info( 'Matched hour' )
                    if itemDate.time().minute == fileMetaDataDate.time().minute:
                        logging.info( 'Matched minute' )
                        return True
        return False

    def rollbackSingleFileOneVersion(self, fileItem):
        """
        Rolls a file back a single version
        :param filename:
        :return:
        """
        logging.info( "Attempting to Rollback file {}".format(fileItem['name']) )
        versionData = self._getFileVersions(fileItem.object_id)
        logging.info( 'Found version data {}'.format(versionData) )

        # Rollback file if there are more than 1 version instances
        if versionData['total_count'] > 1:
            logging.info( 'Rolling file {} to earlier version'.format(fileItem['name']) )
            self._promoteVersion(fileItem, versionData['entries'][1])
        # Otherwise we need to delete the file because there is only 1 file
        else:
            logging.info( 'Deleting file {} since only 1 version was found'.format(fileItem['name']) )
            self._deleteFile(fileItem)


    def _createDictFromCsvFile(self, csvFileName):
        """
        Internally used function to create a dictionary
        out of the csv file with an assumed format.

        The key is the item name
        """
        returnDict = dict()
        with open(csvFileName, 'rb') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                tempDict = dict()
                tempDict['modifiedAt'] = parser.parse(row[0]) # Create Dateobject
                tempDict['modifiedBy'] = row[1]
                tempDict['modifiedByEmail'] = row[2]
                tempDict['ip'] = row[3]
                tempDict['action'] = row[4]
                tempDict['name'] = row[5]
                tempDict['size'] = row[6]
                tempDict['parent'] = row[7]
                tempDict['changeDetails'] = row[8]
                returnDict[row[5]] = tempDict
        return returnDict

    def _promoteVersion(self, fileItem, versionData):
        """
        Promote the version of the file
        :param version:
        :return:
        """
        logging.info( 'Rolling file {} back to version {}'.format(fileItem['name'], versionData) )
        promoteVersionsApi = Constants.PROMOTE_VERSIONS_API.replace('{id}', fileItem.object_id)

        logging.info( 'Promoting version data from api call: {}'.format(promoteVersionsApi) )
        payload = {'type':'file_version', 'id': versionData['id']}
        r = requests.post(promoteVersionsApi, json=payload, headers=self.authHeaders)
        logging.info( 'Return code {}'.format(r.status_code) )
        logging.info( 'Return response {}'.format(r.text) )

        try:
            r.raise_for_status()
        except Exception as e:
            logging.info( 'Version not promoted!' )
            raise e

    def _deleteFile(self, fileItem):
        """
        Deletes a file passed as a parameter
        :param fileItem:
        :return:
        """
        fileApi = Constants.FILE_API.replace('{id}', fileItem.object_id)
        logging.info( 'Deleting resource {}'.format(fileApi) )
        r = requests.delete(fileApi, headers=self.authHeaders)
        logging.info( 'File deleted API returned status code {}'.format(r.status_code) )

        try:
            r.raise_for_status()
        except Exception as e:
            logging.info( 'Error: delete did not work.. on file {}'.format(fileItem['name']) )
            logging.info( 'Error: response text {}'.format(r.text) )
            raise e


if __name__ == "__main__":
    argParser = argParser.ArgumentParser(description='Process a csv file for rollback. '
                                                     'The csv file should have the following columns'
                                                     '(some are not used and can be left empty, but structure is important here):\n'
                                                 '1. Date\n'
                                                 '2. User name\n'
                                                 '3. User email (not used)\n'
                                                 '4. IP Address (not used)\n'
                                                 '5. Action (not used)\n'
                                                 '6. item name (file or folder name)\n'
                                                 '7. Size (not used)\n'
                                                 '8. Parent folder\n'
                                                 '9. Change details\n')
    argParser.add_argument('--csv', dest='csv_file', required=True, help='csv file to process')
    args = argParser.parse_args()
    print "CSVFile Processing {}".format(args.csv_file)
    if (args.csv_file):
        restore = Restore(shouldAuthenticate=True)
        restore.rollbackFilesInCSV(args.csv_file)
    else:
        print "Error: Requires csv_file to process"
        argParser.print_help()


