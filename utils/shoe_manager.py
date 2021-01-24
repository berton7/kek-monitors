import logging
from typing import Any, Dict, List

import pymongo
from configs.config import DB_CONFIG

from utils.shoe_stuff import Shoe
from utils.tools import get_logger


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
		self._db.insert_one(shoe.__dict__)

	def add_shoes(self, shoes: List[Shoe]):
		'''Add these shoes to the database'''
		l = []
		for shoe in shoes:
			l.append(shoe.__dict__)
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
			shoe.__dict__ = item
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
				shoe.__dict__ = item
				shoes.append(shoe)
		return shoes

	def update_shoe(self, shoe: Shoe):
		'''Update the shoe in the db matching the same name.'''
		self._db.update_many({"_Shoe__name": shoe.name}, {"$set": shoe.__dict__})
