import asyncio
import json
import os
from json.decoder import JSONDecodeError
from typing import Any

from configs.config import *

from utils.server.msg import *
from utils.server.server import Server
from utils.tools import get_logger


class Common(Server):
	def __init__(self, logger_name: str, add_stream_handler, socket_path: str):
		self.general_logger = get_logger(
			logger_name + ".General", add_stream_handler)
		self.client_logger = get_logger(logger_name + ".Client", add_stream_handler)

		self.class_name = self.get_class_name()

		super().__init__(logger_name, add_stream_handler, socket_path)

		self._loop_lock = asyncio.Lock()

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

		self._new_whitelist = None  # type: Optional[List[str]]
		self._new_blacklist = None  # type: Optional[List[str]]
		self._new_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self._new_config = None  # type: Optional[Dict[str, Any]]

		self._has_to_quit = False

	def init(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

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
			self.webhooks = self.webhooks
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
			r.error = ERRORS.INVALID_PAYLOAD
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
			r.error = ERRORS.INVALID_PAYLOAD
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
			r.error = ERRORS.INVALID_PAYLOAD
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
			r.error = ERRORS.INVALID_PAYLOAD
			r.info = f"Invalid config (expected dict, got {type(cmd.payload)}"
		return r

	async def main(self):
		pass

	def start(self, delay):
		'''Call this to start the loop.'''
		self.delay = delay
		self._main_task = self._asyncio_loop.create_task(self.main())
		self._asyncio_loop.run_forever()
		self.general_logger.debug("Shutting down...")
