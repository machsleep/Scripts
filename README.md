# Scripts
Some personal scripts?


## BoxScripts

### Restore
This script should be used to restore file versions from an infected box directory. Leveraging the box-sdk (2.0), we've built a small script to take in a list of affected files with various metadata and roll each file back to its previous version -- of course, if there is only 1 version of the file, then that file will be deleted. Since we are using the "versions" api, we invariably assume that the user of this tool has an Enterprise account with Box. 

#### Add Credentials

In Constants.py please change CLIENT_SECRET and CLIENT_ID to your app's credentials.

#### Prepare CSV

CSV file should have the following columns with actual DATA only.

Date,	User's Name,	User's Email,	IP Address,	Action,	Item / Name,	Size,	Contained in Folder,	Change Details

#### Run script
```python
python Restore.py --csv myCsvfile.csv
```
The script will print an HTTP link. This is your auth-url. Paste that link into a Browser. 

Login in to your box account (if it asks you to).

Finally, the browser will try to connect to https://127.0.0.1, since this is the default post-back url. 

You then copy and paste the `code` in the hyperlink to the command prompt and press enter. 

That's it.

#### Dependencies:
##### Requests
http://docs.python-requests.org/en/latest/

`pip install requests`
##### BoxSDK
https://github.com/box/box-python-sdk

`pip install boxsdk`
##### DateUtil
`pip install python-dateutil`
