'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''
import time

from math import sqrt
from statistics import median

from django.conf import settings

# to do: detect language and load all stopwords? P1
from swirl.nltk import sent_tokenize
from swirl.processors.utils import capitalize, capitalize_search, clean_string, has_numeric, highlight_list, match_any, match_all, json_to_flat_string, parse_query, position_dict, remove_numeric, remove_tags, result_processor_feedback_empty_record, result_processor_feedback_merge_records, stem_string
from swirl.spacy import nlp

from swirl.processors.processor import PostResultProcessor, ResultProcessor

from swirl.performance_logger import SwirlRelevancyLogger

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

SWIRL_RELEVANCY_CONFIG = getattr(settings, 'SWIRL_RELEVANCY_CONFIG', {
    'title': {
        'weight': 1.5
    },
    'body': {
        'weight': 1.0
    },
    'author': {
        'weight': 1.0
    }
})

SWIRL_MIN_SIMILARITY = getattr(settings, 'SWIRL_MIN_SIMILARITY', 0.01)
SWIRL_MAX_MATCHES = getattr(settings, 'SWIRL_MAX_MATCHES', 5)
SWIRL_HIGHLIGHT_START_CHAR = getattr(settings, 'SWIRL_HIGHLIGHT_START_CHAR', '*')
SWIRL_HIGHLIGHT_END_CHAR = getattr(settings, 'SWIRL_HIGHLIGHT_END_CHAR', '*')

#############################################
#############################################

class CosineRelevancyResultProcessor(ResultProcessor):

    def __init__(self, results, provider, query_string, request_id='', **kwargs):
        super().__init__(results, provider, query_string, request_id=request_id, **kwargs)

    def process(self):

        logger.debug(f'{self}  processor called with logger name {logger.name}')

        RELEVANCY_CONFIG = SWIRL_RELEVANCY_CONFIG
        dict_result_lens = {}
        list_query_lens = []
        swrel_logger = SwirlRelevancyLogger(self.request_id, self.provider.name +'_'+ str(self.provider.id))
        swrel_logger.start_pass_1()
        self.modified = 0

        if not self.results:
            return self.modified

        parsed_query = parse_query(self.query_string, self.result_processor_json_feedback)
        if len(parsed_query.query_stemmed_target_list) != len(parsed_query.query_target_list):
            pass # self.info(f"parsed query [un]stemmed mismatch : {parsed_query.query_stemmed_target_list} != {parsed_query.query_target_list}")

        list_query_lens.append(len(parsed_query.query_list))
        for item in self.results:
            dict_score = {}
            if 'explain' in item:
                dict_score = item['explain']
                item['dict_score'] = dict_score
                dict_len = {}
                # field length
                # to do: refactor below to avoid duplication of code
                for field in RELEVANCY_CONFIG:
                    if field in item:
                        if type(item[field]) == list:
                            # to do: handle this better
                            item[field] = item[field][0]
                        # result_field is shorthand for item[field]
                        result_field = clean_string(item[field]).strip()
                        # check for zero-length result
                        if result_field:
                            if len(result_field) == 0:
                                continue
                        # prepare result field
                        if result_field.startswith('http'):
                            # the field is a URL, split it on -
                            if '-' in result_field:
                                result_field = result_field.replace('-', ' ')
                        result_field_list = result_field.strip().split()
                        if field in dict_len:
                            self.warning("Duplicate field detected, ignoring")
                        else:
                            dict_len[field] = len(result_field_list)
                        if field in dict_result_lens:
                            dict_result_lens[field].append(len(result_field_list))
                        else:
                            dict_result_lens[field] = []
                            dict_result_lens[field].append(len(result_field_list))
                        # end if
                    # end if
                # end for
                item['dict_len'] = dict_len
                continue

            ############################################
            # result item

            if not 'hits' in item:
                item['hits'] = {}

            dict_score['stems'] = ' '.join(parsed_query.query_stemmed_list)
            dict_len = {}
            notted = ""
            for field in RELEVANCY_CONFIG:
                if field in item:
                    if type(item[field]) == list:
                        # to do: handle this better
                        item[field] = item[field][0]
                    # result_field is shorthand for item[field]
                    # item[field] needs to be a string from this point forward.
                    # code expects this and blows up otherwise.
                    item[field] = json_to_flat_string(item[field],deadman=100)
                    result_field = clean_string(item[field]).strip()
                    # check for zero-length result
                    if result_field:
                        if len(result_field) == 0:
                            continue
                    # prepare result field
                    if result_field.startswith('http'):
                        # the field is a URL, split it on -
                        if '-' in result_field:
                            result_field = result_field.replace('-', ' ')
                    swrel_logger.start_nlp(len(result_field))
                    result_field_nlp = nlp(result_field)
                    swrel_logger.end_nlp()
                    result_field_list = result_field.strip().split()
                    # fix for https://github.com/swirlai/swirl-search/issues/34
                    result_field_stemmed = stem_string(result_field)
                    result_field_stemmed_list = result_field_stemmed.strip().split()
                    if len(result_field_list) != len(result_field_stemmed_list):
                        pass # (f"result field [un]stemmed mismatch : {result_field_list} != {result_field_stemmed_list}")
                    # NOT test
                    for t in parsed_query.not_list:
                        if t.lower() in (result_field.lower() for result_field in result_field_list):
                            notted = {field: t}
                            break
                    # field length
                    if field in dict_len:
                        self.warning(f"duplicate field detected: {field}")
                    else:
                        dict_len[field] = len(result_field_list)
                    if field in dict_result_lens:
                        dict_result_lens[field].append(len(result_field_list))
                    else:
                        dict_result_lens[field] = []
                        dict_result_lens[field].append(len(result_field_list))

                    # initialize
                    dict_score[field] = {}
                    extracted_highlights = []
                    match_stems = []
                    ###########################################
                    # query vs result_field
                    if match_any(parsed_query.query_stemmed_list, result_field_stemmed_list):
                        # capitalize search terms that are capitalied in the result field
                        query = ' '.join(capitalize_search(parsed_query.query_list, result_field_list))
                        swrel_logger.start_nlp(len(query))
                        query_nlp = nlp(query)
                        swrel_logger.end_nlp()
                        # check for zero vector
                        empty_query_vector = False
                        if query_nlp.vector.all() == 0:
                            empty_query_vector = True
                        qvr = 0.0
                        label = '_*'
                        if empty_query_vector or result_field_nlp.vector.all() == 0:
                            if len(result_field_list) == 0:
                                qvr = 0.0
                            else:
                                qvr = 0.3 + 1/3
                            # end if
                        else:
                            swrel_logger.start_sim()
                            if len(sent_tokenize(result_field)) > 1:
                                # by sentence, take highest
                                max_similarity = 0.0
                                for sent in sent_tokenize(result_field):
                                    result_sent_nlp = nlp(sent)
                                    if not result_sent_nlp.has_vector:
                                        qvs = 0.0
                                    else:
                                        qvs = query_nlp.similarity(result_sent_nlp)
                                    if qvs > max_similarity:
                                        max_similarity = qvs
                                # end for
                                qvr = max_similarity
                                label = '_s*'
                            else:
                                qvr = query_nlp.similarity(result_field_nlp)
                            swrel_logger.end_sim()
                        # end if
                        if qvr >= float(SWIRL_MIN_SIMILARITY):
                            dict_score[field]['_'.join(parsed_query.query_list)+label] = qvr
                        else:
                            logger.debug(f"{self}: item below SWIRL_MIN_SIMILARITY: {'_'.join(parsed_query.query_list)+label} ~?= {item}")
                    ############################################
                    # score each query target
                    for stemmed_query_target, query_target in zip(parsed_query.query_stemmed_target_list, parsed_query.query_target_list):
                        query_slice_stemmed_list = stemmed_query_target
                        query_slice_stemmed_len = len(query_slice_stemmed_list)
                        if '_'.join(query_target) in dict_score[field]:
                            # already have this query slice in dict_score - should not happen?
                            self.warning(f"{query_target} already in dict_score")
                            continue
                        ####### MATCH
                        # iterate across all matches, match on stem
                        # match_all returns a list of result_field_list indexes that match
                        match_list = match_all(query_slice_stemmed_list, result_field_stemmed_list)
                        # truncate the match list, if longer than configured
                        if len(match_list) > SWIRL_MAX_MATCHES:
                            match_list = match_list[:SWIRL_MAX_MATCHES-1]
                        qw_list = query_target
                        if match_list:
                            key = ''
                            for match in match_list:
                                extracted_match_list = result_field_list[match:match+query_slice_stemmed_len]
                                # if the extracted match is capitalized, then capitalize the query
                                qw_list = capitalize(qw_list, extracted_match_list)
                                key = '_'.join(extracted_match_list)+'_'+str(match)
                                # extract query window qw around the match
                                if (match-(2*query_slice_stemmed_len)-1) < 0:
                                #     if (match-query_slice_stemmed_len-1) < 0:
                                #         rw_list = result_field_list_rel[match-query_slice_stemmed_len-1:match+(2*query_slice_stemmed_len)+1]
                                #     else:
                                    rw_list = result_field_list[match:match+(3*query_slice_stemmed_len)+1]
                                else:
                                    rw_list = result_field_list[match-(2*query_slice_stemmed_len)-1:match+(2*query_slice_stemmed_len)+1]
                                # end if
                                if not parsed_query.query_has_numeric and has_numeric(rw_list):
                                    rw_list = remove_numeric(rw_list)
                                    if not rw_list:
                                        rw_list = result_field_list[match:match+(3*query_slice_stemmed_len)+1]
                                # end if
                                dict_score[field][key] = 0.0
                                ######## SIMILARITY vs WINDOW
                                rw_nlp = nlp(' '.join(rw_list))
                                if rw_nlp.vector.all() == 0:
                                    dict_score[field][key] = 0.31 + 1/3
                                qw_nlp = nlp(' '.join(qw_list))
                                if qw_nlp.vector.all() == 0:
                                    dict_score[field][key] = 0.32 + 1/3
                                if dict_score[field][key] == 0.0:
                                    qw_nlp_sim = qw_nlp.similarity(rw_nlp)
                                    if qw_nlp_sim:
                                        if qw_nlp_sim >= float(SWIRL_MIN_SIMILARITY):
                                            dict_score[field][key] = qw_nlp_sim
                                        else:
                                            logger.debug(f"{self}: item below SWIRL_MIN_SIMILARITY: {' '.join(qw_list)} ~?= {item}")
                                if dict_score[field][key] == 0.0:
                                    del dict_score[field][key]
                                ######### COLLECT MATCHES FOR HIGHLIGHTING
                                for extract in extracted_match_list:
                                    if extract in extracted_highlights:
                                        continue
                                    extracted_highlights.append(extract)
                                if '_'.join(query_slice_stemmed_list) not in match_stems:
                                    match_stems.append('_'.join(query_slice_stemmed_list))
                            # end for
                        # end if match_list
                    # end for
                    if dict_score[field] == {}:
                        del dict_score[field]
                    ############################################
                    # highlight
                    item[field] = item[field].replace(SWIRL_HIGHLIGHT_START_CHAR,'')   # remove old
                    item[field] = item[field].replace(SWIRL_HIGHLIGHT_END_CHAR,'')   # remove old
                    field_hits = position_dict(remove_tags(item[field]), extracted_highlights)
                    item['hits'][field] = {}
                    item['hits'][field] = field_hits
                    # fix for https://github.com/swirlai/swirl-search/issues/33
                    item[field] = highlight_list(remove_tags(item[field]), extracted_highlights)
                # end if
            # end for field in RELEVANCY_CONFIG:

            if not dict_score:
                logger.debug("No dict_score!")

            if notted:
                item['NOT'] = notted
            else:
                if not 'dict_score' in item:
                    item['dict_score'] = dict_score
                    item['dict_len'] = dict_len
                else:
                    logger.debug("No dict_score in item!!!")
                if not 'dict_len' in item:
                    logger.debug("Missing dict_len!!")

        # end for result in results.json_results:

        # Note the length here beforewe had the feedback below
        self.modified = len(self.results)

        # Add list_query_lens to result processor feedback
        rpf_rec = result_processor_feedback_empty_record()
        rpf_rec["result_processor_feedback"]["query"]["dict_result_lens"] = dict_result_lens
        rpf_rec["result_processor_feedback"]["query"]["list_query_lens"] = list_query_lens
        self.results.append(rpf_rec)
        self.processed_results = self.results
        swrel_logger.complete_pass_1()
        return self.modified

#############################################

class CosineRelevancyPostResultProcessor(PostResultProcessor):

    type = 'CosineRelevancyPostResultProcessor'


    ############################################

    def __init__(self, search_id, request_id = ''):
        self.include_pass_1 = False
        return super().__init__(search_id, request_id=request_id)


    def _pass_2_extract_result_len_stats(self):
        m_rec = result_processor_feedback_empty_record()
        for results in self.results:
            m_rec = result_processor_feedback_merge_records(m_rec, results.result_processor_json_feedback)
        return m_rec.get("result_processor_feedback",{}).get("query",{}).get("dict_result_lens",{}),m_rec.get("result_processor_feedback",{}).get("query",{}).get("list_query_lens",[])

    ############################################
    ############################################

    def process(self):

        RELEVANCY_CONFIG = SWIRL_RELEVANCY_CONFIG

        updated = 0
        dict_result_lens = {}
        list_query_lens = []
        swrel_logger = SwirlRelevancyLogger(self.request_id)

        # compute field means
        dict_len_median = {}
        (dict_result_lens, list_query_lens) = self._pass_2_extract_result_len_stats()

        if not dict_result_lens:
            if self.result_count == 0:
                # not an error
                pass
            else:
                self.error('Dictionary of result lengths is empty. Was CosineRelevancyResultProcessor included in Search Providers Processor configuration?')

        for field in dict_result_lens:
            dict_len_median[field] = median(dict_result_lens[field])
        # compute query length adjustmnet
        # dict_query_lens = {}

        ############################################
        # PASS 2

        # score results by field, adjusting for field length
        highlighted_json_results = []
        swrel_logger.start_pass_2()
        swirl_id = 1
        for results in self.results:
            if not results.json_results:
                continue
            for item in results.json_results:
                item['swirl_id'] = swirl_id
                swirl_id = swirl_id + 1
                if 'swirl_score' in item:
                    logger.debug(f"already scored - {item['url']}")
                item['swirl_score'] = 0.0
                # check for not
                if 'NOT' in item:
                    item['swirl_score'] = -1.0 + 1/3
                    item['explain'] = { 'NOT': item['NOT'] }
                    del item['NOT']
                    break
                # retrieve the scores and lens from pass 1
                dict_score = None
                if 'dict_score' in item:
                    dict_score = item['dict_score']
                    del item['dict_score']
                else:
                    logger.debug("Missing dict_score!")
                if 'dict_len' in item:
                    logger.debug("Found dict_len")
                    dict_len = item['dict_len']
                    del item['dict_len']
                else:
                    logger.debug("Missing dict_len!")
                if 'explain' in item:
                    logger.debug("Found explain")
                    dict_score = item['explain']
                    del item['explain']

                # Check if dict_score is still not defined
                if dict_score is None:
                    self.warning("dict_score is still missing after all attempts to define it!")
                    continue  # Skip to the next iteration

                relevancy_model = ""
                # check for _relevancy_model
                if '_relevancy_model' in item:
                    relevancy_model = item['_relevancy_model']
                    del item['_relevancy_model']
                fs_flag_boost_body = False
                fs_flag_boost_title = False
                if relevancy_model:
                    if relevancy_model == 'FILE_SYSTEM':
                        # if title has no matches, and body does, copy body to title; delete it from explain
                        if not 'title' in dict_score:
                            # no matches on title
                            if 'body' in dict_score:
                                if len(item['body']) > 0:
                                    # match on body, none on title -> use title boost on body
                                    fs_flag_boost_body = True
                    if relevancy_model == 'EVENT':
                        # if body has no matches, and title does, use 2 x title; delete it from explain
                        if not 'body' in dict_score:
                            # no matches on body
                            if 'title' in dict_score:
                                if len(item['title']) > 0:
                                    # match on title, none on body -> use title boost x2
                                    fs_flag_boost_title= True
                # score the item
                dict_len_adjust = {}
                for f in dict_score:
                    if f in RELEVANCY_CONFIG:
                        weight = RELEVANCY_CONFIG[f]['weight']
                        if f == 'body':
                            if fs_flag_boost_body:
                                if 'title' in RELEVANCY_CONFIG:
                                    weight = RELEVANCY_CONFIG['title']['weight']
                                else:
                                    self.warning(f"title field missing when applying relevancy model: FILE_SYSTEM")
                        if f == 'title':
                            if fs_flag_boost_title:
                                if 'title' in RELEVANCY_CONFIG:
                                    weight = RELEVANCY_CONFIG['title']['weight'] * 2.0
                                else:
                                    self.warning(f"title field missing when applying relevancy model: EVENT")
                    else:
                        continue
                    len_adjust = float(dict_len_median[f] / dict_len[f])
                    dict_len_adjust[f] = len_adjust
                    qlen_adjust = float(median(list_query_lens) / len(results.query_string_to_provider.strip().split()))
                    logger.debug(f"score loop driver - {f} - {dict_score[f]} - {item['url']}")
                    for k in dict_score[f]:
                        if k.startswith('_') or k in ('result_length_adjust', 'query_length_adjust'):
                            continue
                        if not dict_score[f][k]:
                            continue
                        if dict_score[f][k] >= float(SWIRL_MIN_SIMILARITY):
                            rank_adjust = 1.0 + (1.0 / sqrt(item['searchprovider_rank']))
                            logger.debug(f"calc swirl_score BEFORE - {item['swirl_score']} - {item['url']}")
                            if k.endswith('_*') or k.endswith('_s*'):
                                item['swirl_score'] = item['swirl_score'] + (weight * dict_score[f][k]) * (len(k) * len(k))
                            else:
                                item['swirl_score'] = item['swirl_score'] + (weight * dict_score[f][k]) * (len(k) * len(k)) * len_adjust * qlen_adjust * rank_adjust
                            logger.debug(f"calc swirl_score AFTER - {item['swirl_score']} - {item['url']}")
                        # end if
                    # end for
                # end for
                for f in dict_score:
                    if f in dict_len_adjust:
                        dict_score[f]['result_length_adjust'] = dict_len_adjust[f]
                        dict_score[f]['query_length_adjust'] = qlen_adjust
                ####### explain
                item['explain'] = dict_score
                item['dict_len'] = dict_len
                possible_hits = item.get('hits', None)
                if possible_hits:
                    item['explain']['hits'] = item['hits']
                    del item['hits']
                else:
                    logger.debug('no hits to move')
                if fs_flag_boost_body:
                    item['explain']['boosts'] = 'FILE_SYSTEM'

                updated = updated + 1
                # save highlighted version
                highlighted_json_results.append(item)
            # end for
            results.save()
        # end for
        ############################################

        self.results_updated = int(updated)
        swrel_logger.complete_pass_2()

        return self.results_updated

#############################################

class DropIrrelevantPostResultProcessor(PostResultProcessor):

    type = 'DropIrrelevantPostResultProcessor'

    def process(self):

        modified = 0

        for results in self.results:
            if not results.json_results:
                continue
            relevant_results = []
            for item in results.json_results:
                # to do: override from tag
                if 'swirl_score' in item:
                    if item['swirl_score'] > settings.MIN_SWIRL_SCORE:
                        relevant_results.append(item)
                    else:
                        modified = modified - 1
                else:
                    modified = modified - 1

            results.json_results = relevant_results
            results.save()

        return modified
