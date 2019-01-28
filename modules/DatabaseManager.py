from pymongo import MongoClient
import gzip
import shutil
import requests
from bs4 import BeautifulSoup as soup
import multiprocessing as mp
import datetime
import re
import pandas as pd
import json
from pprint import pprint
import psutil
import os
import html
import logging
import inspect
import functools
import itertools
import importlib
import pkgutil
import base64
import pysftp
import time
import math
import urllib
import glob
import random
import argparse

import config
from tools import *
from DataGetters import *


class Monitoring:
	memuseme	= lambda : int(psutil.Process(os.getpid()).memory_info()[0] / 2. ** 30 * 1024)
	cpuuseme	= lambda : psutil.Process(os.getpid()).cpu_percent()
	cpuuse	  	= lambda : psutil.cpu_percent()
	memuse	  	= lambda : psutil.virtual_memory()[2]
	logMemory   = lambda : logger.info(f'memory usage : all = {Monitoring.memuse()} %  -  me = {Monitoring.memuseme()} MB')
	logCpu	  	= lambda : logger.info(f'cpu	usage : all = {Monitoring.cpuuse()} %  -  me = {Monitoring.cpuuseme()} % ')


def download_db_link(url):
	logger.critical(f'trying to download url : {url}')

	sftp = ftp_connect()

	new_url = url

	try:
		if re.search(r'.*?youtube\.com/watch.*', url):

			file_name = youtube_downloader.download_music(url, str(int(time.time())))

		else:

			file_name = download(url)


		file_address = f'{os.getcwd()}/{file_name}'

		sftp.put(file_address, f'guessit/download/{file_name}')

		new_url = f'http://51.255.213.191:3002/{file_name}'

		logger.critical(file_address)

		logger.critical('removing file ...')

		os.remove(file_address)

	except Exception as error:
		logger.critical('llll')
		logger.critical(error)

	return new_url


def download_db(db_name):
	db = load_db(db_name)

	for doc in db:

		for field in doc:
			logger.critical(field)
			new_data = []

			items = doc[field] if isinstance(doc[field], list) else [doc[field]]

			if not isinstance(items[0], str) or items[0].find('http') == -1 or items[0].find('87.236.209.215') != -1:
				continue

			for item in items:
				new_data += [download_db_link(item)]

			doc[field] = new_data if isinstance(doc[field], list) else new_data[0]

		save_db(db, db_name)

		#sleep(10)


def update_data(data_name, data):

	for resource in get_resources(data_name):

		data_id_name = f'{resource}ID'

		if data_id_name in data:

			data_id = data[f'{data_id_name}']

			page_link = get_page_link(resource, data_name).format(data_id=data_id)

			logger.info(f'trying to get info from link : {page_link}')

			page = make_soup(page_link)

			#logger.info(str(page)[:1000])

			new_data = {}

			#get_attributes(resource, data_name) + common_attributes

			getter_module = globals()[f'get_{data_name}_data_from_{resource}']

			modules = []

			for local_var in getter_module('get_locals'):
				if callable(getter_module(local_var)):
					modules += [getter_module(local_var)]

			for module in modules:
				try	 : new_data[module.__name__] = module(page)
				except Exception as error : logger.warning(f'no "{module.__name__}" from "{page_link}" becuase {error}')



			#def get_attribute_from_page(page, module):
			#		try:
			#			return (module.__name__, module(page), '')
			#		except Exception as error:
			#			return (module.__name__, '###', error)
			#
			#	attributes = pool.map_async(functools.partial(get_attribute_from_page, page), modules).get()
			#
			#	for attribute, value, error in attributes:
			#		if value != '###':
			#			new_data[attribute] = value
			#		else:
			#			logger.warning(f'no "{attribute}" from "{value}" becuase {error}')

			#logger.info(f'from "{page_link}" page got : {new_data}')

			#data.update(new_data)
			#pprint(new_data)
			for key in new_data: data[key] = new_data[key]
			#pprint(data)

	return data


def load_db(db_name):

	try:
		logger.critical(f'trying to load {db_name} dataset from hard disk...')

		db = json.load(open(f'{config.dataset_dir}/{db_name}db.json', 'r'), encoding='utf-8')

		logger.critical(f'loading {db_name} dataset from hard disk is done.')

	except Exception as error:

		logger.error(error)

		logger.critical(f'could not open dataset from {config.dataset_dir}/ directory')

		logger.critical(f'trying to download {db_name} dataset from server...')

		db = json.loads(requests.get(f'{db_url}{db_name}db.json', 'r').text)

		logger.critical(f'loading {db_name} dataset from server is done.')


	if config.backup:

		logger.critical(f'taking backup from {db_name} dataset ...')

		json.dump(db, open(f"{config.dataset_dir}/{db_name}db {time.ctime().replace(':', '-')}.backup", 'w'), indent=4)

		logger.info(f'taking backup from {db_name} dataset is done.')

	return db


def save_db(db, db_name):
	logger.critical('Writing to file ...')

	json.dump(db, open(f'{config.dataset_dir}/{db_name}db.json', 'w'), indent=4)

	if config.safe_mode:
		json.dump(db, open(f'{config.dataset_dir}/{db_name}dbLastUpdate.json', 'w'), indent=4)

	logger.critical('Writing to file is done.')

	return True


def get_expired_data(db, begin, end):
	old_data = []
	for j in range(begin, end):
		if not 'lastUpdate' in db[j] or not db[j]['lastUpdate'] or not isinstance(db[j]['lastUpdate'], str):
			db[j]['lastUpdate'] = str(time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime(0)))

		if time.strptime(db[j]['lastUpdate'], '%a %b %d %H:%M:%S %Y') < time.localtime(time.time() - config.expiration_time):
			old_data += [db[j]]

	return old_data


def update_db_partial(db, updated_items, begin=0, end=None):
	if end is None:
		end = len(db)

	changes = 0
	for j in range(begin, end):
		updated_data = [data for data in updated_items if data['id'] == db[j]['id']]

		if updated_data:
			updated_data = updated_data[0]
			updated_data['lastUpdate'] = time.ctime()

			for key in updated_data:
				if (key not in db[j] or db[j][key] != updated_data[key]):
					db[j][key] = updated_data[key]
					changes += 1

	return db, changes


def update_db(db_name, begin=0, en                                                                                                                                                        d=None, timeout=10**4):

	db = load_db(db_name)
	if end is None:
		end = len(db)
	else:
		end = min(end, len(db))

	with mp.Pool() as pool:

		for i in range(begin, end, updating_step):

			Monitoring.logMemory()
			Monitoring.logCpu()
			
			logger.critical(f'Updating {db_name} dataset from {i} to {i + updating_step} ...')

			old_data = get_expired_data(db, begin=i, end=min(i + updating_step, end))

			logger.critical('Retrieving data ...')

			updated_items = pool.map_async(functools.partial(globals()['update_data'], db_name), old_data).get()

			logger.critical('Retrieving data is done.')

			db, changes = update_db_partial(db, updated_items, begin=i, end=min(i + updating_step, end))

			if changes > 0:
				save_db(db, db_name)

	logger.critical(f'{db_name} dataset updated successfully :)')


def find_db(db_name, max_find_new=10**4, max_find_all=10**4, max_db_all=10**6, timeout=10**5, save_to_db=True, resources=None):

	start_time = time.time()

	db = load_db(db_name)

	count_find_new, count_find_all = 0, 0

	logger.critical('trying to find new data...')

	changes = 0

	with mp.Pool(process_count) as pool:

		for resource in get_resources(db_name) if resources is None else resources:

			logger.critical(f'trying to find {db_name} data from {resource}.')

			data_id_name = f'{resource}ID'

			datas = [data[data_id_name] for data in db if data_id_name in data]

			resource_links = get_page_link(resource, db_name, f'{db_name}_list')

			logger.critical(f"resource links : {resource_links if len(resource_links) < 3 else str(resource_links[:3]) + '...'} ")

			new_datas, new_datas_all, checked_pages = [], [], []

			if f'collect_{db_name}_id_from_{resource}' not in globals(): break

			while len(db) < max_db_all and count_find_all < max_find_all and count_find_new < max_find_new:

				#print([x[f'{resource}ID'] for x in new_datas_all])

				new_datas, resource_links, checked_pages = zip(*pool.map(functools.partial(globals()[f'collect_{db_name}_id_from_{resource}'], checked_id=[x[f'{resource}ID'] for x in db], checked_pages=checked_pages, timeout=start_time - time.time() + timeout), [resource_links]))

				checked_pages = list(itertools.chain.from_iterable(list(checked_pages)))

				resource_links = list(itertools.chain.from_iterable(list(resource_links)))

				#print(new_datas)

				new_datas = set(list(itertools.chain.from_iterable(list(new_datas))))

				logger.info(new_datas)

				count_find_all += len(new_datas)

				new_datas -= set([x[f'{resource}ID'] for x in db])

				logger.info(new_datas)

				count_find_new += len(new_datas)

				logger.critical(f'finding {db_name} data is done.')

				changes = len(new_datas)

				if save_to_db and changes > 0:
					db +=  [{'id': make_id(data_id), f'{resource}ID': data_id} for data_id in new_datas]
					save_db(db, db_name)


	#logger.critical(f"all new datas {new_datas if len(new_datas) < 3 else str(new_datas[:3]) + '...'}")


	logger.critical(f'{changes} number of new items added to {db_name} dataset successfully :)')

	return new_datas


def init_db(db_name):
	open(f'{config.dataset_dir}/{db_name}db.json', 'w+').write('[]')


def save_pages(url, patterns):
	return

# does not work yet
def load_modules():
	names = ['Amirabbas', 'Kiarash', 'Mohammad']
	for name in names:
		download(f'http://51.255.213.191/guessit/database/DataGetter_{name}.py')
		module_file = importlib.import_module(f'DataGetter_{name}')

		for module in [module for module in dir(module_file) if re.match('get.*', module)]:
			print(module, name)
			globals()[module] = getattr(module_file, module)


def check_get_function(data_name, resource, page_link):
	page = make_soup(page_link)

	getter_module = globals()[f'get_{data_name}_data_from_{resource}']

	modules = []
	new_data = {}
	for local_var in getter_module('get_locals'):
		if callable(getter_module(local_var)):
			modules += [getter_module(local_var)]

	for module in modules:
		try	 : new_data[module.__name__] = module(page)
		except Exception as error : logger.warning(f'no "{module.__name__}" from "{page_link}" becuase {error}')

	pprint(new_data)


def test_getter(data_name, resource, attributes=None, count=None, id_list=None, complete_report=True):
	getter_modules = globals()[f'get_{data_name}_data_from_{resource}']
	if attributes is None: attributes = getter_modules('get_locals')
	db = load_db(data_name)
	count = len(load_db(data_name)) if count is None else count
	sample_data = random.sample(db, count)
	data_ids = id_list if id_list else [new_data[f'{resource}ID'] for new_data in sample_data if f'{resource}ID' in new_data] #find_db(data_name, resources=[resource], save_to_db=False, max_find_all=count)

	test_results = []

	for attribute in attributes:
		
		failed_get_ids, failed_test_ids, all_datas = [], [], []

		for data_id in data_ids:
			page = make_soup(get_page_link(resource, data_name).format(data_id=data_id))
			
			try:
				new_data = getter_modules(attribute)(page, test=True)
				logger.info(f'id = "{data_id}" ------- {attribute} = "{new_data}"')
				if new_data is None: failed_test_ids += [new_data]
				else: all_datas += [new_data]

			except Exception as error:
				failed_get_ids += [data_id]
				logger.error(error)
 
		test_result = {
			'data_name'			: data_name,
			'attribute'			: attribute,
			'resource'			: resource,
			'failed_get_ids'	: failed_get_ids,
			'failed_tests_ids'	: failed_test_ids,
			
			'success_rate'		: str((count - len(failed_get_ids) - len(failed_test_ids)) / count * 100) + '%'
		}
		if complete_report: 
			test_result = dict(list(test_result.items()) + list({
				'all_datas'		: all_datas
			}.items()))

		test_results += [test_result]

	return test_results

"""
def download_resouce_page(resource, db_name):
	with mp.Pool(10) as pool:
		while 1:
				try:
					page_queue = json.load(open(f'{main_dir}/download/page/{resource}/{db_name}/statics.json'))['page_queue']
					break
				except: pass
		step = 10
		for i in range(0, len(page_queue), step):
			while 1:
				try:
					page_queue = json.load(open(f'{main_dir}/download/page/{resource}/{db_name}/statics.json'))['page_queue']
					break
				except: pass
			pool.map(make_soup, page_queue[i:i+step])
"""

def download_resources(resource, db_name, count=float('Inf'), count_founds=float('Inf'), timeout=float('Inf'), page_queue=None, start=0, resume=False):
	start_time = time.time()
	#mp.Process(target=download_resouce_page, args=(resource, db_name, )).start()
	location = f'{main_dir}/download/page/{resource}/{db_name}'
	if resume:
		try:
			statics = json.load(open(f'{location}/statics.json'))
			start = statics['start']
			page_queue = statics['page_queue']
		except: pass
	base = get_page_link(resource, db_name, 'base')
	page_queue = get_page_link(resource, db_name, f'{db_name}_list') if page_queue is None else page_queue
	page_queue_first_len = len(page_queue)
	i = start - 1
	while i < len(page_queue) - 1:
		i += 1
		page = page_queue[i]
		if i % 30 == 0 or i == len(page_queue) - 1: json.dump({'page_queue': page_queue, 'start': i}, open(f'{location}/statics.json', 'w+'), indent=4)
		logger.info(f"i: {i} ------ Founded pages: {len(page_queue)} ------ Saved pages: {len(glob.glob(f'{location}/*.html'))}")
		souped_page = make_soup(page, location=location)
		#if local_save: continue
		patterns = [get_resources()[resource][db_name][x] for x in get_resources()[resource][db_name] if x.endswith('_pattern')]
		for pattern in patterns:
			for url in [tag['href'] for tag in souped_page.find_all('a', {'href':re.compile(pattern)})]:
				absolute_url = urllib.parse.urljoin(base, re.search(pattern, url).group(1))
				if absolute_url not in page_queue:
					page_queue += [absolute_url]
					#print(f'i - start >= count : {i - start >= count}   i = {i}  start = {start}   count = {count}')
					if i - start >= count or len(page_queue) - page_queue_first_len >= count_founds or time.time() - start_time >= timeout:
						return page_queue, i

	logger.critical(f'Downloading resource ended successfully!')


def init_project():
	for resource in get_resources():
		for db_name in get_resources()[resource]:
			directory = f'{main_dir}/download/page/{resource}/{db_name}/'
			if os.path.exists(directory): continue
			try: os.makedirs(directory)
			except Exception as error: logger.error(error)



def arg_parse():
	"""
	"""

	parser = argparse.ArgumentParser()

	parser.add_argument('--test_getter', action='store_true', dest='test_getter',
		            	default=False, help='test getter modules')

	parser.add_argument('--download_resources', action='store_true', dest='download_resources',
		            	default=False, help='download resources')

	parser.add_argument('--update_db', action='store_true', dest='update_db',
		            	default=False, help='updating database')

	parser.add_argument('--find_db', action='store_true', dest='find_db',
		            	default=False, help='finding database id')

	parser.add_argument('--init_db', action='store_true', dest='init_db',
		            	default=False, help='initializing database')

	parser.add_argument('-resource', type=str, dest='resource',
		            	help='resource of test data')

	parser.add_argument('-db', type=str, dest='db',
		            	help='db of test data')

	parser.add_argument('-attributes', type=str, nargs='+', dest='attributes', default=None,
		            	help='attribute of test data')

	parser.add_argument('-count', type=int, dest='count', default=None,
		            	help='number of test datas')

	parser.add_argument('-id', type=str, nargs='+', dest='id',
		            	help='data id s to be tested')

	parser.add_argument('-resume', action='store_true', dest='resume', default=False,
		            	help='specify the resume arg in download_resources function')

	parser.add_argument('-dont_use_local_save', action='store_true', dest='dont_use_local_save', default=False,
		            	help='specify whether should use local saved pages in make_spup funtion or not')

	parser.add_argument('-dont_save_page_local', action='store_true', dest='dont_save_page_local', default=False,
		            	help='specify whether should use local saved pages in make_spup funtion or not')

	parser.add_argument('-complete_report', action='store_true', dest='complete_report', default=False,
		            	help='gives complete eport of task')

	args = parser.parse_args()

	config.use_local_save = not args.dont_use_local_save
	config.save_page_local = not args.dont_save_page_local

	if args.test_getter:
		logger.critical('test results : ')
		pprint(test_getter(args.db, args.resource, args.attributes, count=args.count, id_list=args.id, complete_report=args.complete_report))
	
	elif args.download_resources:
		download_resources(args.resource, args.db, count=args.count, resume=args.resume)

	elif args.update_db:
		update_db(args.db)

	elif args.find_db:
		find_db(args.db)

	elif args.init_db:
		init_db(args.db)


if __name__ == '__main__':
	arg_parse()
	#init_project()