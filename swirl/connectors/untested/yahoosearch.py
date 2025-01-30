
'''
@author:     Harshil Khamar
@contact:    harshilkhamar1@gmail.com
'''

from sys import path
from os import environ

import django

from swirl.utils import swirl_setdir
from serpapi import GoogleSearch
path.append(swirl_setdir()) # path to settings.py file
environ.setdefault('DJANGO_SETTINGS_MODULE', 'swirl_server.settings') 
django.setup()

from django.conf import settings

from celery.utils.log import get_task_logger
from logging import DEBUG, INFO, WARNING
logger = get_task_logger(__name__)

from swirl.connectors.mappings import *
from swirl.connectors.connector import Connector

from datetime import datetime

from serpapi import YahooSearch

class YahooSearch(Connector):

    type = "YahooSearch"

    def __init__(self, provider_id, search_id, update, request_id=''):
        super().__init__(provider_id, search_id, update, request_id)


    def execute_search(self, session=None):
        apikey = None
        if self.provider.credentials:
            apikey = self.provider.credentials
        else:
            if getattr(settings, 'SERPAPI_API_KEY', None):
                apikey = settings.SERPAPI_API_KEY
            else:
                self.found = 0
                self.retrieved = 0
                self.response = []
                self.status = "ERR_NO_CREDENTIALS"
                return

        prompted_query = ""
        if self.query_to_provider.endswith('?'):
            prompted_query = self.query_to_provider
        else:
            if 'p' in self.query_mappings:
                prompted_query = self.query_mappings['p'].format(query_to_provider=self.query_to_provider)
            else:
                prompted_query = self.query_to_provider
                self.warning(f'p not found in query_mappings!')
                
        if not prompted_query:
            self.found = 0
            self.retrieved = 0
            self.response = []
            self.status = "ERR_PROMPT_FAILED"
            return
        
        self.query_to_provider = prompted_query
        params = {
            "p": "coffee",
            "engine": "yahoo",
            "api_key": apikey, 
            "output": "json"
        }
        search = GoogleSearch(params)
        data = search.get_dict()
        completions = data
        message = completions['organic_results'] # FROM API Doc

        self.found = 1
        self.retrieved = 1
        self.response = message

        return

    ########################################

    def normalize_response(self):

        logger.debug(f"{self}: normalize_response()")

        self.results = [
                {
                'title': self.query_string_to_provider,
                'body': f'{self.response}',
                'author': 'YahooSearch',
                'date_published': str(datetime.now())
            }
        ]

        return
