'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''

from sys import path
from os import environ
from datetime import datetime

import time

import django

from swirl.utils import swirl_setdir, http_auth_parse
path.append(swirl_setdir()) # path to settings.py file
environ.setdefault('DJANGO_SETTINGS_MODULE', 'swirl_server.settings')
django.setup()

import requests

from requests.auth import HTTPBasicAuth, HTTPDigestAuth, HTTPProxyAuth
from requests.exceptions import ConnectionError

import urllib.parse
from urllib3.exceptions import NewConnectionError

from jsonpath_ng import parse
from jsonpath_ng.exceptions import JsonPathParserError

from http import HTTPStatus

from celery.utils.log import get_task_logger
from logging import DEBUG, INFO, WARNING
logger = get_task_logger(__name__)

from swirl.connectors.mappings import *
from swirl.connectors.utils import bind_query_mappings

from swirl.connectors.connector import Connector

########################################
########################################

class Requests(Connector):

    type = "Requests"

    ########################################

    def get_method(self):
        return None

    def send_request(self, url, params=None, query=None, **kwargs):
        return dict()

    def construct_query(self):

        """
        Contstruct the query to provider is actually constructing a URL to the provider
        As part of this it handles next page logic. This is approproaye for GET requests
        but less necessary for a POST.

        As such when the self.provider.query_template contains well formed JSON it is a
        assumed that this IS the query string to provider and the and the url will be
        the query to provider.
        """

        logger.debug(f"{self}: construct_query()")

        # to do: migrate this to Connector base class?
        query_to_provider = ""
        if self.provider.credentials.startswith('HTTP'):
            query_to_provider = bind_query_mappings(self.provider.query_template, self.provider.query_mappings, self.provider.url)
        else:
            query_to_provider = bind_query_mappings(self.provider.query_template, self.provider.query_mappings, self.provider.url, self.provider.credentials)
        # this should leave one item, {query_string}
        if '{query_string}' in query_to_provider:
            query_to_provider = query_to_provider.replace('{query_string}', urllib.parse.quote_plus(self.query_string_to_provider))

        if self.search.sort.lower() == 'date':
            # insert before the last parameter, which is expected to be the user query
            sort_query = query_to_provider[:query_to_provider.rfind('&')]
            if 'DATE_SORT' in self.query_mappings:
                sort_query = sort_query + '&' + self.query_mappings['DATE_SORT'] + query_to_provider[query_to_provider.rfind('&'):]
                query_to_provider = sort_query
            else:
                self.warning(f'DATE_SORT missing from self.query_mappings: {self.query_mappings}')
        else:
            sort_query = query_to_provider[:query_to_provider.rfind('&')]
            if 'RELEVANCY_SORT' in self.query_mappings:
                sort_query = sort_query + '&' + self.query_mappings['RELEVANCY_SORT'] + query_to_provider[query_to_provider.rfind('&'):]
                query_to_provider = sort_query

        self.query_to_provider = query_to_provider

        return

    ########################################

    def validate_query(self, session=None):

        logger.debug(f"{self}: validate_query()")

        query_to_provider = self.query_to_provider
        if '{' in query_to_provider or '}' in query_to_provider:
            self.warning(f"{self.provider.id} found braces {{ or }} in query")
            return False

        return super().validate_query()

    ########################################

    def _put_configured_headers(self, headers = None):
        """
        Add any configured headers to any that exist in the input param
        """
        ret_headers = self.provider.http_request_headers
        if headers is not None:
            ret_headers.update(headers)
        return ret_headers

    def execute_search(self, session=None):

        logger.debug(f"{self}: execute_search()")

        # determine if paging is required
        pages = 1
        if 'PAGE' in self.query_mappings:
            if self.provider.results_per_query > 10:
                # yes, gather multiple pages
                pages = int(int(self.provider.results_per_query) / 10)
                # handle remainder
                if (int(self.provider.results_per_query) % 10) > 0:
                    pages = pages + 1

        # issue the query
        start = 1
        mapped_responses = []

        for page in range(0, pages):

            self.warning(f"Page: {page}")

            if 'PAGE' in self.query_mappings:
                page_query = self.query_to_provider[:self.query_to_provider.rfind('&')]
                page_spec = None
                if 'RESULT_INDEX' in self.query_mappings['PAGE']:
                    page_spec = self.query_mappings['PAGE'].replace('RESULT_INDEX',str(start))
                if 'RESULT_ZERO_INDEX' in self.query_mappings['PAGE']:
                    page_spec = self.query_mappings['PAGE'].replace('RESULT_ZERO_INDEX',str(start-1))
                if 'PAGE_INDEX' in self.query_mappings['PAGE']:
                    page_spec = self.query_mappings['PAGE'].replace('PAGE_INDEX',page+1)
                if page_spec:
                    page_query = page_query + '&' + page_spec + self.query_to_provider[self.query_to_provider.rfind('&'):]
                else:
                    self.warning(f"failed to resolve PAGE query mapping: {self.query_mappings['PAGE']}")
                    page_query = self.query_to_provider
            else:
                page_query = self.query_to_provider

            # check the query
            if page_query == "":
                self.error("page_query is blank")
                return

            # dictionary of authentication types permitted in the upcoming eval
            http_auth_dispatch = {'HTTPBasicAuth': HTTPBasicAuth, 'HTTPDigestAuth': HTTPDigestAuth, 'HTTProxyAuth': HTTPProxyAuth}

            response = None
            # issue the query
            try:
                if self.provider.credentials:
                    if session and self.provider.eval_credentials and '{credentials}' in self.provider.credentials:
                        credentials = session[self.provider.eval_credentials]
                        self.provider.credentials = self.provider.credentials.replace('{credentials}', credentials)
                    if self.provider.credentials.startswith('HTTP'):
                        # handle HTTPBasicAuth('user', 'pass') etc
                        http_auth = http_auth_parse(self.provider.credentials)

                        response = self.send_request(page_query, auth=http_auth_dispatch.get(http_auth[0])(*http_auth[1]),query=self.query_string_to_provider,
                                                     headers=self._put_configured_headers())
                    else:
                        if self.provider.credentials.startswith('bearer='):
                            # populate with bearer token
                            headers = {
                                "Authorization": f"Bearer {self.provider.credentials.split('bearer=')[1]}"
                            }
                            response = self.send_request(page_query, headers=self._put_configured_headers(headers), query=self.query_string_to_provider)
                        elif self.provider.credentials.startswith('X-Api-Key='):
                            headers = {
                                "X-Api-Key": f"{self.provider.credentials.split('X-Api-Key=')[1]}"
                            }
                            logger.debug(f"{self}: sending request with auth header X-Api-Key")
                            response = self.send_request(page_query, headers=self._put_configured_headers(headers), query=self.query_string_to_provider)
                            # all others
                        else:
                            response = self.send_request(page_query, query=self.query_string_to_provider, headers=self._put_configured_headers())
                        # end if
                    # end if
                else:
                    # response = requests.get(page_query)
                    response = self.send_request(page_query, query=self.query_string_to_provider, headers=self._put_configured_headers())
            except NewConnectionError as err:
                self.error(f"requests.{self.get_method()} reports {err} from: {self.provider.connector} -> {page_query}", NewConnectionError)
                return
            except ConnectionError as err:
                self.error(f"requests.{self.get_method()} reports {err} from: {self.provider.connector} -> {page_query}")
                return
            except requests.exceptions.InvalidURL as err:
                self.error(f"requests.{self.get_method()} reports {err} from: {self.provider.connector} -> {page_query}")
                return
            if response.status_code != HTTPStatus.OK:
                self.error(f"request.{self.get_method()} returned: {response.status_code} {response.reason} from: {self.provider.name} for: {page_query}")
                return
            # end if

            # normalize the response
            mapped_response = {}
            json_data = response.json()
            if not json_data:
                self.message(f"Retrieved 0 of 0 results from: {self.provider.name}")
                self.retrieved = 0
                self.found = 0
                self.status = 'READY'
                return
            # extract results using mappings
            for mapping in RESPONSE_MAPPING_KEYS:
                if mapping == 'RESULT':
                    # skip for now
                    continue
                if mapping in self.response_mappings:
                    jxp_key = f"$.{self.response_mappings[mapping]}"
                    try:
                        jxp = parse(jxp_key)
                        matches = [match.value for match in jxp.find(json_data)]
                    except JsonPathParserError:
                        self.error(f'JsonPathParser: {err} in provider.self.response_mappings: {self.provider.response_mappings}')
                        return
                    except (NameError, TypeError, ValueError) as err:
                        self.error(f'{err.args}, {err} in provider.self.response_mappings: {self.provider.response_mappings}')
                        return
                    # end try
                    if matches:
                        if len(matches) == 0:
                            # no matches
                            continue
                        if len(matches) == 1:
                            mapped_response[mapping] = matches[0]
                        else:
                            self.error(f'{mapping} is matched {len(matches)} expected 1')
                            return
                    else:
                        # no match, maybe ok
                        pass
                # end if
            # end for
            # count results etc
            found = retrieved = -1
            if 'RETRIEVED' in mapped_response:
                retrieved = int(mapped_response['RETRIEVED'])
                self.retrieved = retrieved
            if 'FOUND' in mapped_response:
                found = int(mapped_response['FOUND'])
                self.found = found
            # check for 0 response
            if found == 0 or retrieved == 0:
                # no results, not an error
                self.message(f"Retrieved 0 of 0 results from: {self.provider.name}")
                self.retrieved = 0
                self.status = 'READY'
                return
            # process the results

            if 'RESULTS' in mapped_response:
                if not mapped_response['RESULTS']:
                    self.warning("1")
                    mapped_response['RESULTS'] = json_data
                if not type(mapped_response['RESULTS']) == list:
                    # nlresearch single result
                    if type(mapped_response['RESULTS']) == dict:
                        tmp_list = []
                        tmp_list.append(mapped_response['RESULTS'])
                        mapped_response['RESULTS'] = tmp_list
                    else:
                        self.error(f"mapped results was type: {type(mapped_response['RESULTS'])}")
                        return
                # end if
            else:
                # check json_data, if it is already a result set, just go with that
                if type(json_data) == list:
                    if len(json_data) > 0:
                        if type(json_data[0]) == dict:
                            self.warning("2")
                            mapped_response['RESULTS'] = json_data
                else:
                    self.error(f'{self}: RESULTS missing from mapped_response')
                    return
                # end if
            # end if
            if 'RESULT' in self.response_mappings:
                for result in mapped_response['RESULTS']:
                    try:
                        jxp_key = f"$.{self.response_mappings['RESULT']}"
                        jxp = parse(jxp_key)
                        matches = [match.value for match in jxp.find(result)]
                    except JsonPathParserError:
                        self.error(f'JsonPathParser: {err} in self.response_mappings: {self.provider.response_mappings}')
                        return
                    except (NameError, TypeError, ValueError) as err:
                        self.error(f'{err.args}, {err} in self.response_mappings: {self.provider.response_mappings}')
                        return
                    # end try
                    if matches:
                        if len(matches) == 1:
                            for match in matches:
                                mapped_responses.append(match)
                        else:
                            self.error(f'control mapping RESULT matched {len(matches)}, expected {self.provider.results_per_query}')
                            return
                    else:
                        # no match, maybe ok
                        pass
            else:
                # no RESULT key specified
                for res in mapped_response['RESULTS']:
                    mapped_responses.append(res)
            # check retrieved
            if mapped_responses:
                # to do: review
                if retrieved > -1 and retrieved != len(mapped_responses):
                    self.warning(f"retrieved != length of response {len(mapped_responses)}")
            else:
                # to do: review
                self.error(f"no results extracted from response! found:{found}")
                if found != 0:
                    found = retrieved = 0
                # end if
            if retrieved == -1:
                # to do: this is probably wrong
                retrieved = len(mapped_responses)
                self.retrieved = retrieved
            if found == -1:
                # for now, assume the source delivered what it found
                found = len(mapped_responses)
                self.found = found
            # check for 0 delivered results (different from above)
            if found == 0 or retrieved == 0:
                # no results, not an error
                self.message(f"Retrieved 0 of 0 results from: {self.provider.name}")
                self.status = 'READY'
                return

            # check count
            if retrieved < 10:
                # no more pages, so don't request any
                break

            start = start + 10 # get only as many pages as required to satisfy provider results_per_query setting, in increments of 10

            time.sleep(1)

        # end for

        self.warning(f"Response len = {len(mapped_responses)}")

        self.found = found
        self.retrieved = retrieved
        self.response = mapped_responses

        return
