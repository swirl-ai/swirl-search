'''
@author:     Sid Probstein
@contact:    sid@swirl.today
'''

import os
import re
import logging as logger
import json
from pathlib import Path
import uuid
import redis
import socket
import sqlite3
from django.core.paginator import Paginator
from django.conf import settings
from django.contrib.auth import get_user_model
from swirl.web_page import PageFetcherFactory
from views import SearchViewSet
from urllib.parse import urlparse


SWIRL_MACHINE_AGENT   = {'User-Agent': 'SwirlMachineServer/1.0 (+http://swirl.today)'}
SWIRL_CONTAINER_AGENT = {'User-Agent': 'SwirlContainer/1.0 (+http://swirl.today)'}


##################################################
##################################################

def safe_urlparse(url):
    ret  = None
    try:
        ret =  urlparse(url)
    except Exception as err:
        print(f'{err} while parsing URL')
    finally:
        return ret
    
def provider_getter():
    conn = sqlite3.connect('../db.sqlite3')
    cur = conn.cursor()
    cur.execute("select * from swirl_searchprovider")
    res = cur.fetchall()
    return res


def is_running_celery_redis():
    """
    check of the celey redis Brokers are available, if any are not
    print a message retrurn false.
    """
    parsed_redis_urls = []
    celery_urls = [settings.CELERY_BROKER_URL, settings.CELERY_RESULT_BACKEND]
    for url in celery_urls:
        if not (purl := safe_urlparse(url)):
            continue
        if not (purl.scheme or purl.scheme.lower() == 'redis'):
            continue
        parsed_redis_urls.append(purl)

    for url in parsed_redis_urls:
        try:
            r = redis.StrictRedis(host=url.hostname, port=url.port, db=0, decode_responses=True)
            response = r.ping()
            if response:
                print(f"{url} checked.")
        except redis.ConnectionError:
            print("Redis is not running or cannot connect!")
            return False
        except Exception as err:
            print("{err} While checking if redis is running")
            return False

    return True

def is_running_in_docker():
    try:
        with open('/proc/1/sched', 'r') as f:
            sched_first_line = f.readline().strip().lower()
            target_string = "sh (1, #threads: 1)".lower()
            return sched_first_line.replace(" ", "") == target_string.replace(" ", "")
    except Exception as err:
        logger.debug(f"{err} while checking for container")
        return False

def get_page_fetcher_or_none(url):
    search_provider_count = provider_getter()
    user = get_user_model()
    user_list = user.objects.all()
    user_count = len(user_list)
    hostname = socket.gethostname()
    domain_name = socket.gethostbyaddr()

    headers = SWIRL_CONTAINER_AGENT if is_running_in_docker() else SWIRL_MACHINE_AGENT
    """
    info is a tuple with 5 elements. 
    info[0] : number of search providers
    info[1] : number of search objects
    info[2] : number of django users
    info[3] : hostname 
    info[4] : domain name
    """
    info = [
        len(search_provider_count), 
        SearchViewSet.report(),
        user_count, 
        hostname,
        domain_name[0]
        ]
    newurl = url_merger(url, info)
    if (pf := PageFetcherFactory.alloc_page_fetcher(url=newurl, options= {
                                                        "cache": "false",
                                                        "headers":headers,
                                                })):
        return pf
    else:
        logger.info(f"No fetcher for {url}")
        return None
    
def url_merger(url, info):
    data = ''
    for inf in info:
        data = data.join("info=")
        data = data.join(inf)
        data = data.join("&")
    url = url.join(data)
    return url

def get_url_details(request):
    if request:
        parsed_url = urlparse(request.build_absolute_uri())
        scheme = parsed_url.scheme
        hostname = parsed_url.hostname
        port = parsed_url.port if parsed_url.port else ""
    else:
        scheme = settings.PROTOCOL
        hostname = settings.HOSTNAME
        port = 8000

    return scheme, hostname, port


CLAZZ_INSTANTIATE_PAT = r'^([A-Z][a-zA-Z0-9_]*)\((.*)\)'
http_auth_clazz_strings = ['HTTPBasicAuth', 'HTTPDigestAuth', 'HTTProxyAuth']
def http_auth_parse(str):
    """
    returns a tule of : 'HTTPBasicAuth'|'HTTPDigestAuth'|'HTTProxyAuth', [<list-of-arguments>]
    """
    if not str:
        return '',[]
    matched = re.match(CLAZZ_INSTANTIATE_PAT, str)
    if matched:
        c = matched.group(1)
        p = matched.group(2)
        if not (p and c in http_auth_clazz_strings) :
            logger.warning(f'unknown http auth class string {c} or missing parameters')
            return '',[]
        return c, [item.strip().strip("'") for item in p.split(',')]
    else:
        return '',[]



def is_valid_json(j):
    try:
        json.loads(j)
    except ValueError:
        return False
    return True

def swirl_setdir():
    # Get the current path and append it to the path
    this_file = str(Path(__file__).resolve())
    # /Users/sid/Code/swirl_server/swirl/utils.py
    # C:\Users\sid\Code\swirl_server\swirl\utils.py
    slash = '\\'
    if '/' in this_file:
        slash = '/'
    this_path = this_file[:this_file.rfind(slash)]
    this_folder = this_path[this_path.rfind(slash)+1:]
    append_path = ""
    if this_folder == "swirl":
        # chop off the swirl
        swirl_server_path = this_path[:this_path.rfind(slash)]
        append_path = swirl_server_path + slash + 'swirl_server' + slash + 'settings.py'
    # end if
    if append_path == "":
        logger.error("swirl_setdir(): error: append_path is empty string!!")
    if not os.path.exists(append_path):
       logger.error("swirl_setdir(): error: append_path does not exist!!")
    return(append_path)

def is_int(value):
    try:
        if not value:
            return False
        int_value = int(value)
        if int_value > 0:
            return True
        return False
    except ValueError:
        return False

def paginate(data, request):
    page = request.GET.get('page')
    items = request.GET.get('items')
    if data and is_int(page) and is_int(items):
        paginator = Paginator(data, items)
        page_obj = paginator.get_page(page)
        return page_obj.object_list
    return data

def select_providers(providers, start_tag, tags_in_query_list):
    """
    - No tags
        + Include all active providers that have default set to true
    - Leading tag
        + Include active providers where the tag is included in their tag list
          regardless of whether the default is true
    - Embedded Tags (with or without leading tag)
        + Include active providers where the tag is included in their tag list
          regardless of if the default is true
    """
    selected_provider_list = []
    default_provider_list = []

    for provider in providers:
        if provider.default:
            default_provider_list.append(provider)
            if start_tag:
                for tag in provider.tags:
                    if tag.lower() == start_tag.lower():
                        selected_provider_list.append(provider)
                # end for
            else:
                selected_provider_list.append(provider)
            # end if
        else:
            ## not a default provider, check the tag match
            if provider.tags:
                for tag in provider.tags:
                    if tag.lower() in [t.lower() for t in tags_in_query_list] or ( start_tag and start_tag.lower() == tag.lower() ) :
                        if provider not in selected_provider_list:
                            selected_provider_list.append(provider)
                        # end if
                    # end if
                # end for
            # end if
        # end if
    # end for

    # For the case of misspelled or non-existent start tag, there can be no providers that match, in that
    # case return all providers that have default == true
    if len(selected_provider_list) == 0:
        selected_provider_list = default_provider_list

    return selected_provider_list

def generate_unique_id():
    return str(uuid.uuid4())

def remove_file(filename):
    if filename and os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as err:
            logger.error(f"Failed to delete file {filename}. Error: {err}")

def make_dir_if_not_exist(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)