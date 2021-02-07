import asyncio
import json
import os
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional

from kekmonitors.config import COMMANDS, ERRORS, GlobalConfig, BaseConfig

from kekmonitors.utils.server.msg import Cmd, Response, okResponse, badResponse
from kekmonitors.utils.server.server import Server
from kekmonitors.utils.tools import get_logger
import __main__
import pymongo
from pymongo.collection import Collection


def mark_as(_type: str, name: str, path: str, client: Collection):
	existing = client[_type].find_one({"name": name})
	if not existing:
		client[_type].insert_one({"name": name, "path": path})
	else:
		if existing["path"] != path:
			raise Exception(
				f"Trying to register new {_type} ({name}) when it already exists in the database with a different path: {existing['path']}")


class Common(Server):
	def __init__(self, config: BaseConfig, is_monitor: bool):
		self.general_logger = get_logger(
			config.name + ".General", config.add_stream_handler)
		self.client_logger = get_logger(
			config.name + ".Client", config.add_stream_handler)

		self.class_name = self.get_class_name()

		super().__init__(config.name,
                   config.add_stream_handler, os.path.sep.join([GlobalConfig.socket_path, config.name]))

		self.db_client = pymongo.MongoClient(GlobalConfig.db_path)[
                    GlobalConfig.db_name]["register"]

		self._loop_lock = asyncio.Lock()
		#self._stop_event = asyncio.Event()

		self.cmd_to_callback[COMMANDS.SET_WHITELIST] = self.on_set_whitelist
		self.cmd_to_callback[COMMANDS.SET_BLACKLIST] = self.on_set_blacklist
		self.cmd_to_callback[COMMANDS.SET_WEBHOOKS] = self.on_set_webhooks
		self.cmd_to_callback[COMMANDS.SET_CONFIG] = self.on_set_config
		self.cmd_to_callback[COMMANDS.GET_WHITELIST] = self.on_get_whitelist
		self.cmd_to_callback[COMMANDS.GET_BLACKLIST] = self.on_get_blacklist
		self.cmd_to_callback[COMMANDS.GET_WEBHOOKS] = self.on_get_webhooks
		self.cmd_to_callback[COMMANDS.GET_CONFIG] = self.on_get_config

		if is_monitor:
			self.whitelist_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "monitors/whitelists.json"])
			self.blacklist_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "monitors/blacklists.json"])
			self.config_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "monitors/configs.json"])
			self.webhooks_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "monitors/webhooks.json"])
		else:
			self.whitelist_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "scrapers/whitelists.json"])
			self.blacklist_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "scrapers/blacklists.json"])
			self.config_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "scrapers/configs.json"])
			self.webhooks_filepath = os.path.sep.join(
				[GlobalConfig.config_path, "scrapers/webhooks.json"])

		self.whitelist = self.load_config(self.whitelist_filepath)
		self.blacklist = self.load_config(self.blacklist_filepath)
		self.webhooks = self.load_config(self.webhooks_filepath)
		self.config = self.load_config(self.config_filepath)

		self._new_whitelist = None  # type: Optional[List[str]]
		self._new_blacklist = None  # type: Optional[List[str]]
		self._new_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self._new_config = None  # type: Optional[Dict[str, Any]]

		self._has_to_quit = False

	def init(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	async def async_init(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	def on_shutdown(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	async def on_async_shutdown(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	def get_class_name(self):
		'''Internal function used to get the correct filename.'''
		'''Not necessary, but sometimes you might want to override this.'''
		return type(self).__name__

	def _mark_as_monitor(self):
		mark_as("Monitors", self.class_name, __main__.__file__, self.db_client)

	def _mark_as_scraper(self):
		mark_as("Scrapers", self.class_name, __main__.__file__, self.db_client)

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
		if self._new_blacklist is not None:
			self.general_logger.info(f"New blacklist: {self._new_blacklist}")
			self.blacklist = self._new_blacklist
			self._new_blacklist = None
		if self._new_whitelist is not None:
			self.general_logger.info(f"New whitelist: {self._new_whitelist}")
			self.whitelist = self._new_whitelist
			self._new_whitelist = None
		if self._new_webhooks is not None:
			self.general_logger.info(f"New webhooks: {self._new_webhooks}")
			self.webhooks = self._new_webhooks
			self._new_webhooks = None
		if self._new_config is not None:
			self.general_logger.info(f"New config: {self._new_config}")
			self.config = self._new_config
			self._new_config = None

	async def on_set_whitelist(self, cmd: Cmd) -> Response:
		r = badResponse()
		whitelist = cmd.payload
		if isinstance(whitelist, list):
			self._new_whitelist = whitelist
			self.client_logger.debug("Got new whitelist")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new whitelist but it was invalid: {whitelist}")
			r.error = ERRORS.BAD_PAYLOAD
			r.info = f"Invalid whitelist (expected list, got {type(cmd.payload)}"
		return r

	async def on_set_blacklist(self, cmd: Cmd) -> Response:
		r = badResponse()
		blacklist = cmd.payload
		if isinstance(blacklist, list):
			self._new_blacklist = blacklist
			self.client_logger.debug("Got new blacklist")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new blacklist but it was invalid: {blacklist}")
			r.error = ERRORS.BAD_PAYLOAD
			r.info = f"Invalid blacklist (expected list, got {type(cmd.payload)}"
		return r

	async def on_set_webhooks(self, cmd: Cmd) -> Response:
		r = badResponse()
		webhooks = cmd.payload
		if isinstance(webhooks, dict):
			self._new_webhooks = webhooks
			self.client_logger.debug("Got new webhooks")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new webhooks but it was invalid: {webhooks}")
			r.error = ERRORS.BAD_PAYLOAD
			r.info = f"Invalid webhooks (expected dict, got {type(cmd.payload)}"
		return r

	async def on_set_config(self, cmd: Cmd) -> Response:
		r = badResponse()
		config = cmd.payload
		if isinstance(config, dict):
			self._new_config = config
			self.client_logger.debug("Got new config")
			r = okResponse()
		else:
			self.client_logger.warning(
				f"Got new config but it was invalid: {config}")
			r.error = ERRORS.BAD_PAYLOAD
			r.info = f"Invalid config (expected dict, got {type(cmd.payload)}"
		return r

	async def on_get_config(self, cmd: Cmd) -> Response:
		r = okResponse()
		r.payload = self.config
		return r

	async def on_get_whitelist(self, cmd: Cmd) -> Response:
		r = okResponse()
		r.payload = self.whitelist
		return r

	async def on_get_blacklist(self, cmd: Cmd) -> Response:
		r = okResponse()
		r.payload = self.blacklist
		return r

	async def on_get_webhooks(self, cmd: Cmd) -> Response:
		r = okResponse()
		r.payload = self.webhooks
		return r

	async def main(self):
		pass

	def start(self, delay):
		'''Call this to start the loop.'''
		self.delay = delay
		self._main_task = self._asyncio_loop.create_task(self.main())
		self._asyncio_loop.run_forever()
		self.general_logger.debug("Shutting down...")
