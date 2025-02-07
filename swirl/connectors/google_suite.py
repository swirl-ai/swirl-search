from sys import path
from os import environ

import django

from swirl.utils import swirl_setdir
path.append(swirl_setdir())  # path to settings.py file
environ.setdefault('DJANGO_SETTINGS_MODULE', 'swirl_server.settings')
django.setup()

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

from swirl.connectors.utils import get_search_obj, get_mappings_dict
from swirl.connectors.requestsget import RequestsGet
from swirl.connectors.requestspost import RequestsPost


########################################
########################################

DEFAULT_DATESORT_X = "createdDateTime desc"


class GoogleSuite(RequestsGet):
    """
    Connector to Google Suite
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Get the Google Suite API endpoint
        self.api_endpoint = "https://www.googleapis.com/drive/v3"

    def get_access_token(self):
        """
        Get an OAuth2 access token for Google Suite
        """

        # Replace the following values with your own OAuth2 credentials
        CLIENT_ID = self.config["client_id"]
        CLIENT_SECRET = self.config["client_secret"]
        REDIRECT_URI = self.config["redirect_uri"]

        url = "https://accounts.google.com/o/oauth2/token"
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": "",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=payload, headers=headers)
        return response.json()["access_token"]

    def search(self, query):
        """
        Search Google Suite
        """

        # Get an access token
        access_token = self.get_access_token()

        # Search Google Suite
        url = self.api_endpoint + "/search"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        payload = {
            "query": query,
            "fields": "files(id, name, mimeType, createdTime, modifiedTime)",
        }
        response = requests.post(url, json=payload, headers=headers)

        # Return the results
        return response.json()

    def get_file_by_id(self, file_id):
        """
        Get a file by ID
        """

        # Get an access token
        access_token = self.get_access_token()

        # Get the file
        url = self.api_endpoint + f"/files/{file_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.get(url, headers=headers)

        # Return the file
        return response.json()

    def get_file_content(self, file_id):
        """
        Get the content of a file
        """

        # Get an access token
        access_token = self.get_access_token()

        # Get the file content
        url = self.api_endpoint + f"/files/{file_id}/?alt=media"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.get(url, headers=headers)

        # Return the file content
        return response.content

    def get_mappings(self):
        """
        Get the mappings for Google Suite
        """

        return get_mappings_dict(GOOGLE_SUITE_MAPPINGS)

