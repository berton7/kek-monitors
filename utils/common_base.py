if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

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

		super().__init__(logger_name, socket_path)

		self.cmd_to_callback[COMMANDS.SET_WHITELIST] = self.on_set_whitelist
		self.cmd_to_callback[COMMANDS.SET_BLACKLIST] = self.on_set_blacklist
		self.cmd_to_callback[COMMANDS.SET_WEBHOOKS] = self.on_set_webhooks
		self.cmd_to_callback[COMMANDS.SET_CONFIG] = self.on_set_config

		self.new_whitelist = None  # type: Optional[List[str]]
		self.new_blacklist = None  # type: Optional[List[str]]
		self.new_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self.new_config = None  # type: Optional[Dict[str, Any]]

		self.has_to_quit = False
		self.class_name = self.get_class_name()
		self.filename = self.get_filename()

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
