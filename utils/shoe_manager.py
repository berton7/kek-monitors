import logging
from typing import Any, Dict, List, Union

import pymongo
from configs.config import DB_CONFIG

from utils.shoe_stuff import Shoe
from utils.tools import get_logger


def _change_keys(d, _from, _to):
	if isinstance(d, list):
		new_list = []
		for element in d:
			new_list.append(_change_keys(element, _from, _to))
		return new_list
	elif isinstance(d, dict):
		new_dict = {}
		for key, value in d.items():
			value = _change_keys(value, _from, _to)
			new_key = key
			if isinstance(key, str) and _from in key:
				new_key = key.replace(_from, _to)
			new_dict[new_key] = value
		return new_dict
	else:
		return d


def sanitize(d: Union[Dict[Any, Any], List[Any]]) -> Union[Dict[Any, Any], List[Any]]:
	"""
	Converts keys with "." to "_dot_", as it's not possile to add keys with a "." in MongoDBc
	"""
	return _change_keys(d, ".", "_dot_")


def unsanitize(d: Union[Dict[Any, Any], List[Any]]) -> Union[Dict[Any, Any], List[Any]]:
	"""
	Converts keys with "_dot_" back to "."
	"""
	return _change_keys(d, "_dot_", ".")


class ShoeManager(object):
	'''Manages the database. Mostly a MongoDB wrapper.'''

	def __init__(self, logger: logging.Logger):
		# get a new logger if not provided
		if not logger:
			self._logger = get_logger("ShoeManager")
		else:
			self._logger = logger

		self.db_name = DB_CONFIG.DEFAULT_DB_NAME
		self.db_path = DB_CONFIG.DEFAULT_DB_PATH

		self._client = pymongo.MongoClient(self.db_path)
		self._db = self._client[self.db_name]["items"]
		self._logger.debug("Database initialized.")

	def add_shoe(self, shoe: Shoe):
		'''Add this shoe to the database'''
		self._db.insert_one(sanitize(shoe.__dict__))

	def add_shoes(self, shoes: List[Shoe]):
		'''Add these shoes to the database'''
		l = []
		for shoe in shoes:
			l.append(sanitize(shoe.__dict__))
		self._db.insert_many(l)

	def find_shoe(self, query: Dict[str, Any]):
		'''Find a shoe passing ```query``` to pymongo's find_one'''
		q = {}
		for k in query:
			if not k.startswith("_Shoe__"):
				q[f"_Shoe__{k}"] = query[k]
			else:
				q[k] = query[k]
		item = self._db.find_one(q, {"_id": 0})
		if item:
			shoe = Shoe()
			shoe.__dict__ = unsanitize(item)
			return shoe
		else:
			return None

	def find_shoes(self, query: Dict[str, Any]):
		'''Find all shoes passing ```query``` to pymongo's find_one'''
		q = {}
		for k in query:
			if not k.startswith("_Shoe__"):
				q[f"_Shoe__{k}"] = query[k]
			else:
				q[k] = query[k]
		items = self._db.find(q, {"_id": 0})
		shoes = []
		for item in items:
			if item:
				shoe = Shoe()
				shoe.__dict__ = unsanitize(item)
				shoes.append(shoe)
		return shoes

	def update_shoe(self, shoe: Shoe):
		'''Update the shoe in the db matching the same link.'''
		self._db.update_many({"_Shoe__link": shoe.link}, {
		                     "$set": sanitize(shoe.__dict__)})
