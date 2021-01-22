if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

import json
from json.decoder import JSONDecodeError
from configs.config import *
import os
from typing import Any
from utils.server.server import Server
from utils.tools import get_logger
from utils.server.msg import *


class Common(Server):
	def __init__(self, logger_name: str, socket_path: str):
		self.general_logger = get_logger(logger_name + ".General")
		self.client_logger = get_logger(logger_name + ".Client")

		self.class_name = self.get_class_name()
		self.filename = self.get_filename()

		super().__init__(logger_name, socket_path)

		self.cmd_to_callback[COMMANDS.SET_WHITELIST] = self.on_set_whitelist
		self.cmd_to_callback[COMMANDS.SET_BLACKLIST] = self.on_set_blacklist
		self.cmd_to_callback[COMMANDS.SET_WEBHOOKS] = self.on_set_webhooks
		self.cmd_to_callback[COMMANDS.SET_CONFIG] = self.on_set_config

		self.default_configs_file_path = ["configs", "monitors", "configs.json"]
		self.default_webhooks_file_path = ["configs", "monitors", "webhooks.json"]
		self.default_whitelists_file_path = [
			"configs", "monitors", "whitelists.json"]
		self.default_blacklists_file_path = [
			"configs", "monitors", "blacklists.json"]

		self.whitelist = self.load_config(
			os.path.sep.join(self.default_whitelists_file_path))  # type List[str]
		self.blacklist = self.load_config(os.path.sep.join(
			self.default_blacklists_file_path))  # type: List[str]
		self.webhooks = self.load_config(os.path.sep.join(
			self.default_webhooks_file_path))  # type: Dict[str, Dict[str, Any]]
		self.config = self.load_config(os.path.sep.join(
			self.default_configs_file_path))  # type: Dict[str, Any]

		self.new_whitelist = None  # type: Optional[List[str]]
		self.new_blacklist = None  # type: Optional[List[str]]
		self.new_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self.new_config = None  # type: Optional[Dict[str, Any]]

		self.has_to_quit = False

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

	def load_config(self, path):
		with open(path, "r") as f:
			try:
				j = json.load(f)
			except JSONDecodeError:
				self.general_logger.exception(f"{path} is not valid json. Quitting.")
				exit(1)
			if self.class_name not in j:
				self.general_logger.warning(
					f"{self.class_name} not in {path}, continuing with empty entry.")
				return {}
			else:
				return j[self.class_name]

	def update_local_config(self):
		if self.new_blacklist is not None:
			self.general_logger.info(f"New blacklist: {self.new_blacklist}")
			self.blacklist = self.new_blacklist
			self.new_blacklist = None
		if self.new_whitelist is not None:
			self.general_logger.info(f"New whitelist: {self.new_whitelist}")
			self.whitelist = self.new_whitelist
			self.new_whitelist = None
		if self.new_webhooks is not None:
			self.general_logger.info(f"New webhooks: {self.new_webhooks}")
			self.webhooks = self.webhooks
			self.new_webhooks = None
		if self.new_config is not None:
			self.general_logger.info(f"New config: {self.new_config}")
			self.config = self.new_config
			self.new_config = None

	async def on_set_whitelist(self, cmd: Cmd) -> Response:
		r = badResponse()
		whitelist = cmd.payload
		if isinstance(whitelist, list):
			self.new_whitelist = whitelist
			self.client_logger.debug("Got new whitelist")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new whitelist but it was invalid: {whitelist}")
			r.reason = "Invalid whitelist"
		return r

	async def on_set_blacklist(self, cmd: Cmd) -> Response:
		r = badResponse()
		blacklist = cmd.payload
		if isinstance(blacklist, list):
			self.new_blacklist = blacklist
			self.client_logger.debug("Got new blacklist")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new blacklist but it was invalid: {blacklist}")
			r.reason = "Invalid blacklist"
		return r

	async def on_set_webhooks(self, cmd: Cmd) -> Response:
		r = badResponse()
		webhooks = cmd.payload
		if isinstance(webhooks, dict):
			self.new_webhooks = webhooks
			self.client_logger.debug("Got new webhooks")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new webhooks but it was invalid: {webhooks}")
			r.reason = "Invalid webhooks"
		return r

	async def on_set_config(self, cmd: Cmd) -> Response:
		r = badResponse()
		config = cmd.payload
		if isinstance(config, dict):
			self.new_config = config
			self.client_logger.debug("Got new config")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new config but it was invalid: {config}")
			r.reason = "Invalid config"
		return r

	async def main(self):
		pass

	def start(self, delay):
		'''Call this to start the loop.'''
		self.delay = delay
		self.asyncio_loop.run_until_complete(self.main())
