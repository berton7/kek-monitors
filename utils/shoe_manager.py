import os
import pickle

from utils.shoe_stuff import Shoe
from utils.tools import get_logger

from typing import List, Optional, Union


class ShoeManager(object):
	'''As the name implies this manages the shoe database. Currently it does so by storing the current shoes list for the website
	in a *.pickle file. This is insecure, but easy to implement and manage. You could probably replace it with a fully-fledged database
	like MongoDB etc.'''

	def __init__(self, filename: str, logger=None):
		filename += ".pickle"
		# create variables for the current db name, path, etc.
		splits = filename.split(os.path.sep)
		splits.insert(0, "db")
		self.db_name = splits[-1]
		self.db_path = os.path.sep.join(splits[:-1])
		self.full_db_path = os.path.sep.join([self.db_path, self.db_name])
		# get a new logger if not provided
		if not logger:
			self.logger = get_logger("ShoeManager")
		else:
			self.logger = logger

		# generate db if it doesn't exist
		self.logger.debug("Reading all shoes from " + self.db_name + "...")
		if not os.path.exists(self.full_db_path):
			self.logger.debug("File does not exist, creating it now...")
			os.makedirs(self.db_path, exist_ok=True)
			with open(self.full_db_path, "w") as wf:
				pass
			self.shoes = []  # type: List[Shoe]
		else:
			try:
				with open(self.full_db_path, "rb") as rf:
					self.shoes = pickle.load(rf)
			except EOFError:
				self.shoes = []
		self.logger.debug("Read " + str(len(self.shoes)) +
                    " shoes from " + self.db_name)

	def add_shoe(self, shoe: Shoe):
		# the key in shoe.sizes can only be a string
		for size in shoe.sizes:
			if not isinstance(size, str):
				raise Exception("Cannot insert non-strings sizes (" +
                                    shoe.link + " - " + str(size) + ")")
		self.shoes.insert(0, shoe)

	def find_shoe_by_link(self, link: str) -> Union[Shoe, None]:
		if not isinstance(link, str):
			raise Exception("Cannot search non-string links (" + str(link) + ")")

		# get the first shoe matching the link
		for shoe in self.shoes:
			if shoe.link == link:
				return shoe
		return None

	def find_shoe(self, shoe: Shoe) -> Union[Shoe, None]:
		if not isinstance(shoe, Shoe):
			raise Exception("Argument was not a shoe but a " + type(shoe))
		if not isinstance(shoe.name, str):
			raise Exception("Name is not a string.")
		if not isinstance(shoe.link, str):
			raise Exception("Link is not a string.")
		for current_shoe in self.shoes:
			if shoe.name == current_shoe.name and shoe.link == current_shoe.link:
				return current_shoe
		return None

	def update_shoe(self, shoe: Shoe, move_to_top: bool = True):
		if not isinstance(shoe, Shoe):
			raise Exception("Argument was not a shoe but a " + type(shoe))
		if not isinstance(shoe.name, str):
			raise Exception("Name is not a string.")
		if not isinstance(shoe.link, str):
			raise Exception("Link is not a string.")
		for index, current_shoe in enumerate(self.shoes):
			if shoe.name == current_shoe.name and shoe.link == current_shoe.link:
				self.shoes.remove(current_shoe)
				# useful when dialing with a high number of shoes
				if move_to_top:
					self.shoes.insert(0, shoe)
				else:
					self.shoes.insert(index, shoe)
				return

	def update_db(self):
		with open(self.full_db_path, "wb") as wf:
			pickle.dump(self.shoes, wf, pickle.HIGHEST_PROTOCOL)
		self.logger.debug("Written " + str(len(self.shoes)) + " shoes to file")
