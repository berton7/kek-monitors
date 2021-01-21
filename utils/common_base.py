if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import os
import json
import tornado.httpclient
from typing import Tuple, Any
from utils.tools import get_logger
from utils.server.msg import *


class Common(object):
	def __init__(self, logger_name: str):
		self.general_logger = get_logger(logger_name + ".General")
		self.client_logger = get_logger(logger_name + ".Client")

		self.has_to_quit = False
		self.class_name = self.get_class_name()
		self.filename = self.get_filename()

		self.asyncio_loop = asyncio.get_event_loop()
		tornado.httpclient.AsyncHTTPClient.configure(
			"tornado.curl_httpclient.CurlAsyncHTTPClient")
		self.t_async_client = tornado.httpclient.AsyncHTTPClient()
		self.t_sync_client = tornado.httpclient.HTTPClient()

	def init(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	def get_filename(self):
		'''YOU MUST OVERRIDE ME!!! Copy and paste me. Needed to get the correct filename.'''
		# take current path, split, get last element (=filename), remove ".py"
		return __file__.split(os.path.sep)[-1][:-3]

	def get_class_name(self):
		'''Internal function used to get the correct filename.'''
		'''Not necessary, but sometimes you might want to override this.'''
		return type(self).__name__

	def update_vars_from_file(self, old_var, old_file_var, default_value, should_create_entry=True, *args) -> Tuple[Any, Any, Any]:
		'''Weird function to update the configs from the files, checking if the configs are correct json and keeping backups.'''
		# TODO: make this more readable, simplify it, possibly remove it
		should_create_entry = True
		var = None
		with open(os.path.sep.join(args), "r") as rf:
			try:
				json_file = json.load(rf)
			except json.JSONDecodeError:
				self.general_logger.warning(f"Failed to decode {args[-1]}.")
				if old_file_var:
					self.general_logger.warning(f"Falling back to old {args[-1]}")
					if old_var:
						var = old_var
					elif self.filename in old_file_var:
						var = old_file_var[self.filename]
					else:
						self.general_logger.warning(f"Falling back to empty {args[-1]}.")
						var = default_value
					return var, old_var, old_file_var
				else:
					self.general_logger.warning(f"Falling back to empty {args[-1]}.")
					var = default_value
					return var, old_var, old_file_var
			old_file_var = json_file
			if self.filename not in json_file:
				if should_create_entry:
					self.general_logger.warning(
						f"{self.filename} not present in {args[-1]}. Creating empty entry.")
					with open(os.path.sep.join(args), "w") as wf:
						var = old_var = old_file_var[self.filename] = default_value
						wf.write(json.dumps(old_file_var))
				else:
					self.general_logger.warning(f"{self.filename} not present in {args[-1]}.")
			else:
				old_var = var = json_file[self.filename]
		return var, old_var, old_file_var

	def start(self, delay):
		'''Call this to start the scraper loop.'''
		self.delay = delay
		self.asyncio_loop.run_until_complete(self.main())

	async def main(self):
		return
