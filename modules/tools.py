from bs4 import BeautifulSoup as soup
from pymongo import MongoClient
import modules.config as config
import multiprocessing as mp
from pprint import pprint

import pandas as pd
import functools
import importlib
import datetime
import requests
import logging
import inspect
import pkgutil
import base64
import shutil
import gzip
import json
import html
import time
import glob
import argparse
import sys
import os
import re


download_page_dir 	= f'{config.main_dir}/download/page'


def collect_data_id_from_resource(pages, base, patterns):
    """general finding ids from list pages """

    new_ids = []

    for page in pages:

        souped_page = make_soup(page)

        for pattern in patterns:
            new_pages = [tag['href'] for tag in souped_page.find_all('a', {'href': re.compile(f'({base})?{pattern}')})]

            new_pages =  [base + page if page.find('http') == -1 else page for page in new_pages]

            new_pages =  [page for page in new_pages if page[5:].find('http') == -1]

            new_pages =  [re.sub(r'/?\?.*', '', page) for page in new_pages]
        
            new_ids += [re.search(f'{base}{pattern}', page).group(1) for page in new_pages]
    
    return new_ids


def wait_to_connect(timeout=10, delay=2):
    connected = False
    while not connected:
        try:
            getPage('https://www.google.com', timeout=timeout)
            connected = True
        except:
            connected = False
            time.sleep(delay)
            print('no internet connection')


def get_resource_from_url(url):
    """getting resource of a url"""
    resources = []
    for resource in get_resources().keys():
        for db in list(get_resources()[resource].keys()):
            if 'base' in get_resources()[resource][db]:
                if any([get_resources()[resource][db]['base'] in url]):
                    resources.append(resource)
    if len(resources) > 0:
        return resources[0]
    else:
        return None


def get_db_name_from_url(url):
    """getting db_name of a url"""
    db_name = []
    resource = get_resource_from_url(url)
    if not resource :
        return None
    for db in get_resources()[resource].keys():
        for key , pattern in get_resources()[resource][db].items():
            if 'pattern' in key:
                if any([re.search(pattern, url)]):
                    db_name.append(db)
    if len(db_name) > 0:
        return db_name[0]
    else:
        return None


def download(url, local_filename=None):
    if local_filename is None:
        local_filename = url.split('/')[-1]
    else:
        local_filename += '/' + url.split('/')[-1]

    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename


def make_soup(url):
    """for new urls create the soup file and save it in downloaded pages 
    and for old urls loads soup file for them from files in memory"""
    resource = get_resource_from_url(url)
    db_name = get_db_name_from_url(url)
    if resource and db_name:
        guessed_location = f'{download_page_dir}/{resource}/{db_name}'
    else:
        guessed_location = f'{download_page_dir}/others'
        
        
    location = guessed_location
    file_address = f"{location}/{base64.b64encode(url.encode()).decode().replace('/', '-')}.html"
    
    if os.path.isfile(file_address):
        page_source = open(file_address, encoding='utf-8').read()
    else:
        page_source = get_page(url)
        try: 
            open(file_address, 'w+', encoding='utf-8').write(page_source)
        except Exception as error:
            logger.error(error)
        
    return soup(page_source , 'html.parser')    


def get_page(url, try_count=10, delay=0):
    """get request to url by diffrent options"""
    
    logger.debug(f'get_page started with url={url}, try_count={try_count}, delay={delay}')

    proxies = [{
                "http": None,
                "https": None,
              }]

    content = ''
    for i in range(try_count):
        try	 :
            content = requests.get(url, proxies=proxies[i % len(proxies)]).text
            break
        except Exception as error :
            if logger: logging.error(f'{url} : {error}')
            if logger: logging.info(f'could not get the page. trying again for {i}th time...')
            time.sleep(delay)

    if not content:
        if logger: logging.error(f'get_page FAILED! , could not get the page at last after {try_count} times of trying!')

    return content


def make_id(data_id):

    return base64.b32encode(str(data_id).encode()).decode()


def get_resources(data_name=None):
    
    if data_name is None:
        return config.resources
    else:
        return [resource for resource in config.resources.keys() if data_name in config.resources[resource]]


"""
if __name__ == '__main__':

    url = 'https://sofifa.com/team/245716'
    try:

        resource = [resource for resource in get_resources().keys() if any([get_resources()[resource][db]['base'] in url for db in list(get_resources()[resource].keys()) if 'base' in get_resources()[resource][db]])][0] 
        print(resource)

        db_name = [db for db in get_resources()[resource].keys() if any([re.search(pattern, url) for key, pattern in get_resources()[resource][db].items() if 'pattern' in key])][0]
        guessed_location = f'{download_page_dir}/{resource}/{db_name}'
        print(guessed_location, db_name)
    except Exception as error:
        guessed_location = download_page_dir
        print(error)
"""