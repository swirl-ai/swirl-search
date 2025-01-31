'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''
import json as stdjson


from datetime import datetime
from jsonpath_ng import parse
from jsonpath_ng.exceptions import JsonPathParserError

from swirl.processors.processor import ResultProcessor
from swirl.processors.result_map_converter import ResultMapConverter
from swirl.processors.utils import create_result_dictionary, extract_text_from_tags, str_safe_format, result_processor_feedback_provider_query_terms,date_str_to_timestamp
from swirl.swirl_common import RESULT_MAPPING_COMMANDS

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


#############################################
#############################################


import re
from re import error as re_error

class MappingResultProcessor(ResultProcessor):

    type="MappingResultProcessor"

    def __init__(self, results, provider, query_string, request_id='', **kwargs):
        super().__init__(results, provider, query_string, request_id=request_id, **kwargs)

    def put_query_terms_from_provider(self, swirl_key, text, lBuf):
        """ remember query terms from the hihglight field of each result"""
        if not ( swirl_key and text ):
            return
        if swirl_key not in ('title_hit_highlights','body_hit_highlights'):
            return
        for teaser_text in text:
            hits = extract_text_from_tags(teaser_text, 'em')
            for hit in hits:
                lBuf.append(str(hit).lower())


    def process(self):

        logger.debug(f'mapping processor called with logger name {logger.name}')

        list_results = []
        provider_query_term_results = []
        # result_block = ""

        json_types = [str,int,float,list,dict]
        use_payload = True
        file_system = False
        event = False
        if 'NO_PAYLOAD' in self.provider.result_mappings:
            use_payload = False
        if 'FILE_SYSTEM' in self.provider.result_mappings:
            file_system = True
        if 'EVENT' in self.provider.result_mappings:
            event = True

        result_number = 1
        for result in self.results:
            swirl_result = create_result_dictionary()
            payload = {}
            # report searchprovider rank, not ours
            swirl_result['searchprovider_rank'] = result_number
            swirl_result['date_retrieved'] = str(datetime.now())
            #############################################
            # mappings are in form swirl_key=source_key, where source_key can be a json_string e.g. _source.customer_full_name
            if self.provider.result_mappings:
                mappings = self.provider.result_mappings.split(',')
                for mapping in mappings:
                    stripped_mapping = mapping.strip()
                    # control codez NO_PAYLOAD, FILE_SYSTEM
                    if stripped_mapping in RESULT_MAPPING_COMMANDS:
                        # ignore, values were set above
                        continue
                    # extract source_key=swirl_key
                    swirl_key = ""
                    if '=' in stripped_mapping:
                        # no need to switch to rfind, since multiple = is not allowed
                        # source key may be a json path
                        swirl_key = stripped_mapping[:stripped_mapping.find('=')]
                        source_key = stripped_mapping[stripped_mapping.find('=')+1:]
                    else:
                        source_key = stripped_mapping
                    # control codez
                    if swirl_key.isupper():
                        # to do: check the result mappings list???
                        # if swirl_key == 'BLOCK':
                        #     result_block = source_key
                        # else:
                            # ignore for now
                        continue
                    # check for field list |
                    source_field_list = []
                    if '|' in source_key:
                        source_field_list = source_key.split('|')
                        # self.warning(f"source_field_list! {source_field_list}")
                    if len(source_field_list) == 0:
                        source_field_list.append(source_key)
                    #############################################
                    # check for template
                    template_list = []
                    if source_key.startswith("'"):
                        try:
                            template_list = re.findall(r'\{.*?\}', source_key)
                        except re_error as err:
                            self.error(f"re: {err} while finding all in source key : {source_key}")
                            return []
                        # end try
                    else:
                        for key in source_field_list:
                            template_list.append('{' + key + '}')
                    # search for source_keys & construct a result_dict
                    result_dict = {}
                    # self.warning(f"template_list: {template_list}")
                    for k in template_list:
                        uc = ResultMapConverter(f'$.{k[1:-1]}')  # Use the new combined class
                        jxp_key = uc.get_key()
                        try:
                            jxp = parse(jxp_key)
                            # search result for this
                            matches = [uc.get_value(match.value) for match in jxp.find(result)]
                        except JsonPathParserError as err:
                            self.error(f'JsonPathParser: {err} in jsonpath_ng.find: {jxp_key}')
                            return []
                        except (NameError, TypeError, ValueError) as err:
                            self.error(f'{err.args}, {err} in jsonpath_ng.find: {jxp_key}')
                            return []
                        # end try
                        if len(matches) == 1:
                            result_dict[k[1:-1]] = matches[0]
                        else:
                            result_dict[k[1:-1]] = matches
                    if source_key.startswith("'"):
                        # template
                        bound_template =  str_safe_format(source_key, result_dict)
                        if swirl_key:
                            if swirl_key in swirl_result:
                                swirl_result[swirl_key] = bound_template[1:-1]
                            # end if
                        # end if
                    else:
                        #############################################
                        # single mapping
                        for source_key in source_field_list:
                            if source_key in result_dict:
                                if not result_dict[source_key]:
                                    # blank key
                                    continue
                                if swirl_key:
                                    # provider specifies the target
                                    if swirl_key in swirl_result:
                                        if not type(result_dict[source_key]) in json_types:
                                            if 'date' in source_key.lower():
                                                # parser.parse will fill-in a missing time portion etc
                                                result_dict[source_key] = date_str_to_timestamp(result_dict[source_key])
                                            else:
                                                result_dict[source_key] = str(result_dict[source_key])
                                            # end if
                                        # end if
                                        if type(swirl_result[swirl_key]) == type(result_dict[source_key]):
                                            # same type, copy it
                                            if 'date' in swirl_key.lower() and not 'display' in swirl_key.lower():
                                                if swirl_result[swirl_key] == "":
                                                    swirl_result[swirl_key] = date_str_to_timestamp(result_dict[source_key])
                                                else:
                                                    payload[swirl_key+"_"+source_key] = date_str_to_timestamp(result_dict[source_key])
                                                # end if
                                            else:
                                                if not swirl_result[swirl_key]:
                                                    swirl_result[swirl_key] = result_dict[source_key]
                                                    self.put_query_terms_from_provider(swirl_key,
                                                                                   swirl_result[swirl_key],
                                                                                   provider_query_term_results)
                                                else:
                                                    payload[swirl_key+"_"+source_key] = result_dict[source_key]
                                                # end if
                                        else:
                                            # not same type, convert it
                                            if 'date' in swirl_key.lower() and not 'display' in swirl_key.lower():
                                                if swirl_result[swirl_key] == "":
                                                    if type(result_dict[source_key]) == int:
                                                        # check for int vs long fix for DS-320
                                                        if result_dict[source_key] > 2147483647:
                                                            swirl_result[swirl_key] = str(datetime.fromtimestamp(result_dict[source_key]/1000))
                                                        else:
                                                            swirl_result[swirl_key] = str(datetime.fromtimestamp(result_dict[source_key]))
                                                        # end if
                                                    if type(result_dict[source_key]) == float:
                                                        swirl_result[swirl_key] = str(datetime.fromtimestamp(result_dict[source_key]))
                                                # end if
                                            if type(swirl_result[swirl_key]) == str and type(result_dict[source_key]) == list:
                                                swirl_result[swirl_key] = ' '.join(result_dict[source_key])
                                            # different type, so payload it
                                            if use_payload:
                                                payload[swirl_key] = result_dict[source_key]
                                        # end if
                                    else:
                                        if use_payload:
                                            # to do: check type!!!
                                            if type(result_dict[source_key]) not in [str, int, list, dict]:
                                                payload[swirl_key] = str(result_dict[source_key])
                                            else:
                                                payload[swirl_key] = result_dict[source_key]
                                        # end if
                                    # end if
                                else:
                                    # no target key specified, so it will go into payload with that name
                                    # since it was specified we do not check NO_PAYLOAD
                                    if type(result_dict[source_key]) not in [str, int, list, dict]:
                                        payload[source_key] = str(result_dict[source_key])
                                    else:
                                        payload[source_key] = result_dict[source_key]
                                # end if
                            else:
                                # no results for this mapping were found - normal
                                pass
                            # end if
                        # end for
                # end for
            # end if

            #############################################
            # copy remaining fields, avoiding collisions
            for key in result.keys():
                if key in swirl_result.keys():
                    if not swirl_result[key]:
                        swirl_result[key] = result[key]
                else:
                    if use_payload:
                        if not type(result[key]) in json_types:
                            result[key] = str(result[key])
                        payload[key] = result[key]
                        # end if
                    # end if
            # end for

            # if no date_published, set it to unknown
            # TO DO: maybe this should be left blank? P1 *****
            if swirl_result['date_published'] == "":
                swirl_result['date_published'] = 'unknown'

            #############################################
            # connector specific
            # remove <matched_term> tags from title (northernlight)
            if '<matched_term>' in swirl_result['title']:
                swirl_result['title'] = swirl_result['title'].replace('<matched_term>', '')
                swirl_result['title'] = swirl_result['title'].replace('</matched_term>', '')

            if 'LC_URL' in self.provider.result_mappings:
                self.warning("LC_URL!")
                swirl_result['url'] = swirl_result['url'].lower()

            #############################################
            # final assembly
            if payload:
                swirl_result['payload'] = payload
            # if result_block:
            #     swirl_result['result_block'] = result_block
            # try to find a title, if none provided
            if swirl_result['title'] == "":
                if swirl_result['url']:
                    swirl_result['title'] = swirl_result['url']
                elif swirl_result['author']:
                    swirl_result['title'] = swirl_result['author']
                # end if
            # end if
            # mark results from SearchProviders with result_mapping FILE_SYSTEM
            if file_system:
                swirl_result['_relevancy_model'] = 'FILE_SYSTEM'
            if event:
                swirl_result['_relevancy_model'] = 'EVENT'
            swirl_result['searchprovider'] = self.provider.name
            list_results.append(swirl_result)
            result_number = result_number + 1
            # stop if we have enough results
            if result_number > self.provider.results_per_query:
                # self.warning("Truncating extra results, found & retrieved may be incorrect")
                break
            # unique list of terms from highlights
        # end for

        fb = result_processor_feedback_provider_query_terms(provider_query_term_results)
        if fb:
            list_results.append(fb)

        self.processed_results = list_results
        self.modified = len(self.processed_results)
        return self.modified

#############################################

#############################################

from swirl.data_profiler import profile_data, find_closest_median_most_populated_field, find_longest_most_populated_field, list_by_population_desc, filter_elements_case_insensitive
from swirl.processors.utils import get_tag

class AutomaticPayloadMapperResultProcessor(ResultProcessor):

    type="AutomaticPayloadMapperResultProcessor"

    def process(self):

        # Assumptions: no data has been mapped, most fields are empty, payload is populated
        # Goal: find fields in payload that are suitable for Swirl schema, and copy them

        if not self.results:
            return 0

        result_profile = profile_data(self.results)
        if 'str' in result_profile:
            if 'title' in result_profile['str']:
                if result_profile['str']['title']['Population %'] > 0:
                    logger.debug(f"title is unexpectedly populated {result_profile['str']['title']['Population %']}")
            if 'body' in result_profile['str']:
                if result_profile['str']['body']['Population %'] > 0:
                    logger.debug(f"body is unexpectedly populated {result_profile['str']['title']['Population %']}")
        if 'dict' in result_profile:
            if 'payload' in result_profile['dict']:
                if result_profile['dict']['payload']['Population %'] < 80.0:
                    logger.debug(f"payload is unexpectedly unpopulated {result_profile['dict']['payload']['Population %']}")

        list_payloads = [d['payload'] for d in self.results if 'payload' in d]
        payload_profile = profile_data(list_payloads)
        if not payload_profile:
            self.warning("Payload profile is unexpectedly empty")
            return 0

        to_body = to_title = to_date = to_url = to_author = None

        MAX_TITLE_LEN = get_tag('MAX_TITLE_LEN', self.provider_tags)
        if not MAX_TITLE_LEN:
            MAX_TITLE_LEN = 100
        TITLE_MEDIAN_LEN = get_tag('TITLE_MEDIAN_LEN', self.provider_tags)
        if not TITLE_MEDIAN_LEN:
            TITLE_MEDIAN_LEN = 50

        ###########################
        # find fields

        # find title/body
        if 'str' in payload_profile:
            if len(payload_profile['str']) > 0:
                if len(payload_profile['str']) == 1:
                    # only 1 str
                    (field, profile), = payload_profile['str'].items()
                    if 'Max' in profile:
                        if profile['Max'] < MAX_TITLE_LEN:
                            to_title = field
                        else:
                            to_body = field
                    else:
                        # log error
                        pass
                else:
                    # 2 or more str
                    to_title = find_closest_median_most_populated_field(payload_profile['str'],TITLE_MEDIAN_LEN)
                    to_body = find_longest_most_populated_field(payload_profile['str'])
                    if to_title == to_body:
                        # find another choice for body
                        str_fields = list_by_population_desc(payload_profile['str'])
                        for f in str_fields:
                            if not f == to_title:
                                to_body = f
                                break
                        to_body = None

        if not to_title:
            if 'int' in payload_profile:
                int_fields = list_by_population_desc(payload_profile['int'])
                if int_fields:
                    to_title = int_fields[0]

        if not to_title:
            if 'float' in payload_profile:
                float_fields = list_by_population_desc(payload_profile['float'])
                if float_fields:
                    to_title = float_fields[0]

        # date
        if 'date' in payload_profile:
            date_list = list_by_population_desc(payload_profile['date'])
            if date_list:
                to_date = date_list[0]

        # url
        if 'url' in payload_profile:
            to_url = list_by_population_desc(payload_profile['url'])
            if to_url:
                to_url = to_url[0]

        automapped_fields = []
        if to_title:
            automapped_fields.append(to_title)
        if to_body:
            automapped_fields.append(to_body)
        if to_url:
            automapped_fields.append(to_url)
        if to_date:
            automapped_fields.append(to_date)
        if to_author:
            automapped_fields.append(to_author)

        field_scan_list = filter_elements_case_insensitive(self.results[0]['payload'].keys(),self.results[0].keys())

        ###########################

        handle_dataset = False
        if 'DATASET' in self.provider.result_mappings:
            dataset = []
            handle_dataset = True

        ###########################
        # auto map

        automapped_results = []
        for item in self.results:
            # check for name matches, first, never overwriting
            # note data_profiler detects date using field name, but only for candidacy
            for k in item:
                if k == 'payload':
                    continue
                if k in item['payload']:
                    if not item[k]:
                        if type(item['payload'][k]) == str:
                            item[k] = item['payload'][k]
                            automapped_fields.append(k)
                            self.warning("copying payload field {k}")
                for f in field_scan_list:
                    if f.startswith(k) or f.endswith(k):
                        if not item[k]:
                            if type(item['payload'][f]) == str:
                                item[k] = item['payload'][f]
                                automapped_fields.append(f)
                                self.warning("copying payload field {f}")

            # copy automapped fields, never overwriting
            if to_title:
                if not item['title']:
                    item['title'] = str(to_title) + ": " + str(item['payload'][to_title])
            if to_body:
                if not item['body']:
                    item['body'] = str(to_body) + ": " + str(item['payload'][to_body])
            if to_url:
                if not item['url']:
                    item['url'] = str(item['payload'][to_url])
            if to_date:
                 item['date_published'] = date_str_to_timestamp(item['payload'][to_date])

            # remove automapped_fields from item['payload']
            # to do: this might have to be adjusted depending on what works above
            if 'payload' in item:
                if not handle_dataset:
                    # if handling dataset, leave in payload
                    for field in automapped_fields:
                        del item['payload'][field]

            ###########################
            # filter the payload, remove objects etc

            clean_payload = {}
            for k in item['payload']:
                if type(item['payload'][k]) in [str, int, float]:
                    clean_payload[k] = item['payload'][k]
                if type(item['payload'][k]) == list:
                    if type(item['payload'][k][0]) in [str, int, float]:
                        clean_payload[k] = item['payload'][k]
            if clean_payload:
                item['payload'] = clean_payload

            if handle_dataset:
                if len(automapped_results) == 0:
                    # first item, store it
                    item_1 = item
                    # fix the title
                    item_1['title'] = self.query_string
                    k_list = []
                    for k in clean_payload:
                        k_list.append(k)
                    dataset.append(k_list)
                v_list = []
                for k in clean_payload:
                    v_list.append(clean_payload[k])
                dataset.append(v_list)
            else:
                # save finished item normally
                automapped_results.append(item)

        if handle_dataset:
            if item_1 and dataset:
                if 'payload' in item_1:
                    item_1['payload']['dataset'] = dataset
                self.processed_results = [item_1]
                return 1

        self.processed_results = automapped_results
        self.modified = len(self.processed_results)
        return self.modified
