'''
@author:     Sid Probstein
@contact:    sidprobstein@gmail.com
@version:    SWIRL Preview3
'''

import logging as logger

#############################################    
#############################################    

from swirl.models import Search, Result
from .utils import highlight

def generic_relevancy_processor(search_id):

    module_name = 'generic_relevancy_processor'

    if Search.objects.filter(id=search_id).exists():
        search = Search.objects.get(id=search_id)
        if search.status == 'POST_RESULT_PROCESSING':
            results = Result.objects.filter(search_id=search_id)
        else:
            logger.warning(f"{module_name}: search {search_id} has status {search.status}, this processor requires: status == 'POST_RESULT_PROCESSING'")
            return 0
        # end if
    else:
        logger.error(f"{module_name}: search {search_id} was not found")
        return 0
    # end if

    highlight_field_list = [ 'title', 'body', 'url', 'author' ]
    # max score: +1 per field (4), +1 per double per field (4), +2 for title

    updated = 0
    for result in results:
        highlighted_json_results = []
        if result.json_results:
            for item in result.json_results:
                score = 0
                # highlight & score fields
                for field in highlight_field_list:
                    if item[field]:
                        old_len = len(item[field])
                        item[field] = highlight(item[field], search.query_string_processed)
                        if len(item[field]) > old_len:
                            # something matched this field
                            score = score + 1
                            if '* *' in str(item[field]):
                                # this field appears to have at least one double match
                                score = score + 1
                            if field == 'title':
                                # title boost
                                score = score + 2
                            # end if
                        # end if
                    # end if
                # end for  
                item['score'] = score
                updated = updated + 1
                highlighted_json_results.append(item)
            # end for
            logger.info(f"Updating results: {result.id}")
            result.json_results = highlighted_json_results
            result.save()
        # end if
    # end for

    return updated

#############################################    
#############################################    

from math import sqrt, isnan
 
def squared_sum(x):
    """ return 3 rounded square rooted value """
 
    return round(sqrt(sum([a*a for a in x])),3)

#############################################    

def cos_similarity(x,y):
    """ return cosine similarity between two lists """
    """ can return NaN (not a number) if one of the embeddings is a zero-array - caller must handle """

    numerator = sum(a*b for a,b in zip(x,y))
    denominator = squared_sum(x)*squared_sum(y)
    return round(numerator/float(denominator),3)

#############################################    

from .utils import clean_string_alphanumeric
import spacy

def cosine_relevancy_processor(search_id):

    module_name = 'cosine_relevancy_processor'

    if Search.objects.filter(id=search_id).exists():
        search = Search.objects.get(id=search_id)
        if search.status == 'POST_RESULT_PROCESSING' or search.status == 'RESCORING':
            results = Result.objects.filter(search_id=search_id)
        else:
            logger.warning(f"{module_name}: search {search_id} has status {search.status}, this processor requires: status == 'POST_RESULT_PROCESSING'")
            return 0
        # end if
    else:
        logger.error(f"{module_name}: search {search_id} was not found")
        return 0
    # end if

    RELEVANCY_CONFIG = {
        'title': {
            'weight': 3.0
        },
        'body': {
            'weight': 1.0
        },
        'author': {
            'weight': 2.0
        }
    }

    # note: do not use url as it is usually a proxy vote for title
    
    nlp = spacy.load('en_core_web_md')
    # prep query string
    query_string_nlp = nlp(clean_string_alphanumeric(search.query_string_processed)).vector

    ############################################
    # main loop

    updated = 0
    for result in results:
        highlighted_json_results = []
        if result.json_results:
            for item in result.json_results:
                weighted_score = 0.0
                dict_score = {}
                match_dict = {}
                item['boosts'] = []
                for field in RELEVANCY_CONFIG:
                    if field in item:
                        last_term = ""
                        ############################################
                        # highlight 
                        if not search.status == 'RESCORING':
                            item[field] = highlight(item[field], search.query_string_processed)
                        ############################################
                        # summarize matches
                        for term in search.query_string_processed.strip().split():
                            if term.lower() in item[field].lower():
                                if field in match_dict:
                                    match_dict[field].append(term)
                                else:
                                    match_dict[field] = []
                                    match_dict[field].append(term)
                                # end if
                            # check for bi-gram match
                            if last_term:
                                if not term.lower() == last_term.lower():
                                    if f'*{last_term.lower()}* *{term.lower()}*' in item[field].lower():
                                        if f"{last_term}_{term}" not in match_dict[field]:
                                            match_dict[field].append(f"{last_term}_{term}")
                            last_term = term
                        # end for
                       ############################################
                        # cosine similarity between query and matching field store in dict_score
                        if field in match_dict:
                            # hit!!
                            # dict_score[field + "_field"] = clean_string_alphanumeric(item[field])
                            field_nlp = nlp(clean_string_alphanumeric(item[field])).vector
                            if field_nlp.all() == 0 or query_string_nlp.all() == 0:
                                item['boosts'].append("X_BLANK_EMBEDDING")
                                dict_score[field] = 0.5
                            else:
                                dict_score[field] = cos_similarity(query_string_nlp, field_nlp)
                                if isnan(dict_score[field]):
                                    item['boosts'].append("X_COSINE_NAAN")
                                    dict_score[field] = 0.5
                            # end if
                        # end if
                    # end if
                # end for 
                ############################################
                # weight field similarity
                item['score'] = 0.0
                weight = 0.0
                for field in dict_score:
                    if not field.endswith('_field'):
                        item['score'] = float(item['score']) + float(RELEVANCY_CONFIG[field]['weight']) * float(dict_score[field])
                        weight = weight + float(RELEVANCY_CONFIG[field]['weight'])
                    # end if
                # end for
                if weight == 0.0:
                    item['boosts'].append('X_WEIGHT_0')
                    item['score'] == 0.5
                    weighted_score = 0.5
                else:
                    weighted_score = round(float(item['score'])/float(weight),2)
                    item['score'] = weighted_score
                ############################################
                # boosting                
                query_len = len(search.query_string_processed.strip().split())
                term_match = 0
                phrase_match = 0
                all_terms = 0
                for match in match_dict:
                    terms_field = 0
                    for hit in match_dict[match]:
                        if '_' in hit:
                            phrase_match = phrase_match + 1
                        else:
                            term_match = term_match + 1
                            terms_field = terms_field + 1
                    # boost if all terms match this field
                    # to do: no all_terms_match for a single term query
                    # to do: miami look at ----->
                    if terms_field == query_len and query_len > 1:
                        all_terms = all_terms + 1
                # take away credit for one field, one term hit
                if term_match == 1:
                    term_match = 0
                    term_boost = 0.0
                else:
                    term_boost = round((float(term_match) * 0.1) / float(query_len), 2)
                    item['boosts'].append(f'term_match {term_boost}')
                phrase_boost = round((float(phrase_match) * 0.2) / float(query_len), 2)
                if phrase_boost > 0:
                    item['boosts'].append(f'phrase_match {phrase_boost}')
                all_terms_boost = round((float(all_terms) * 0.1 * float(query_len)), 2)
                if all_terms_boost > 0:
                    item['boosts'].append(f'all_terms {all_terms_boost}')
                item['score'] = item['score'] + max([term_boost, phrase_boost, all_terms_boost])
                item['score'] = round(item['score'], 2)
                ###########################################
                # check for overrun
                if item['score'] > 1.0:
                    item['score'] = 1.0
                # explain
                item['explain'] = {} 
                item['explain']['matches'] = match_dict
                item['explain']['similarity'] = weighted_score
                item['explain']['boosts'] = item['boosts']
                # clean up 
                del item['boosts']
                if search.status == 'RESCORING':
                    if 'score_all_key_phrases' in item:
                        del item['score_all_key_phrases']
                ##############################################
                updated = updated + 1
                highlighted_json_results.append(item)
            # end for
            # logger.info(f"Updating results: {result.id}")
            # save!!!!
            result.json_results = highlighted_json_results
            # to do: catch invalid json error P2
            result.save()
        # end if
    # end for

    return updated
