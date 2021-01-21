# path hack
if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

import argparse
import asyncio
import copy
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

import utils.tools
from configs.config import *
from utils import discord_embeds, shoe_stuff
from utils.common_base import Common
from utils.network_utils import NetworkUtils
from utils.server.msg import *
from utils.server.server import Server
from utils.shoe_manager import ShoeManager
from utils.shoe_stuff import Shoe
from utils.webhook_manager import WebhookManager


class BaseMonitor(Common, NetworkUtils, Server):
	def __init__(self, add_stream_handler: bool = True):
		# init some internal variables (logger, links)
		logger_name = f"Monitor.{self.get_class_name()}"
		self.general_logger = utils.tools.get_logger(
			logger_name, add_stream_handler=add_stream_handler)

		super().__init__(logger_name)
		super(Common, self).__init__(logger_name)
		super(NetworkUtils, self).__init__(
			logger_name, f"{SOCKET_PATH}/Monitor.{self.class_name}")

		self.cmd_to_callback[SET_LINKS] = self.on_set_links
		self.cmd_to_callback[ADD_LINKS] = self.on_add_links

		self.buffer_links = []  # type: List[str]
		self.new_links = []  # type: List[str]
		self.links = []  # type: List[str]
		self.shoes = []  # type: List[Shoe]

		# init config related variables
		# you can change the path for the config files here
		self.default_configs_file_path = ["configs", "monitors", "configs.json"]
		self.default_webhooks_file_path = ["configs", "monitors", "webhooks.json"]
		self.default_whitelists_file_path = [
			"configs", "monitors", "whitelists.json"]
		self.default_blacklists_file_path = [
			"configs", "monitors", "blacklists.json"]
		self.whitelist = None  # type: Optional[List[str]]
		self.old_whitelist = None  # type: Optional[List[str]]
		self.old_whitelists = None  # type: Optional[Dict[str, List[str]]]
		self.blacklist = None  # type: Optional[List[str]]
		self.old_blacklist = None  # type: Optional[List[str]]
		self.old_blacklists = None  # type: Optional[Dict[str, List[str]]]
		self.webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self.old_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
		self.old_webhooks_file = None
		self.config = None  # type: Optional[Dict[str, Any]]
		self.old_config = None  # type: Optional[Dict[str, Any]]
		self.old_configs_file = None  # type: Optional[Dict[str, Dict[str, Any]]]

		self.shoe_manager = ShoeManager(self.filename, logger=self.general_logger)
		self.webhook_manager = WebhookManager(
			self.general_logger.name, add_stream_handler)

		# website-specific variables should be declared here
		self.init()

	def get_filename(self):
		'''YOU MUST OVERRIDE ME! Needed to get the correct filename.'''
		# take current path, split, get last element (=filename), remove ".py"
		return __file__.split(os.path.sep)[-1][:-3]

	def init(self):
		'''Override this in your website-specific monitor, if needed.'''
		pass

	async def on_set_links(self, msg: Cmd) -> Response:
		self.server_logger.debug("Got cmd set_links")
		response = badResponse()
		p = msg.get_payload()
		if p is not None:
			if isinstance(p, list):
				self.new_links = p
				response.set_success(True)
			else:
				self.general_logger.warning(
					"Received new set of links, but payload was not a list: ", p)
				response.set_reason("Payload was not a list")

		else:
			self.general_logger.warning(
				"Failed to decode payload; msg: ", msg.to_json())
			response.set_reason("Failed to decode payload")
		return response

	async def on_add_links(self, msg: Cmd) -> Response:
		self.server_logger.debug("Got cmd add_links")
		response = badResponse()
		p = msg.get_payload()
		if p is not None:
			if isinstance(p, list):
				self.buffer_links = p
				response.set_success(True)
			else:
				self.general_logger.warning(
					"Received new added links, but payload was not a list: ", p)
				response.set_reason("Payload was not a list")

		else:
			self.general_logger.warning(
				"Failed to decode payload; msg: ", msg.to_json())
			response.set_reason("Failed to decode payload")
		return response

	async def on_server_stop(self):
		self.has_to_quit = True
		return okResponse()

	async def get_links(self):
		socket_path = f"{SOCKET_PATH}/Scraper.{self.class_name}"
		self.general_logger.debug("Getting links...")

		cmd = Cmd()
		cmd.set_cmd(GET_LINKS)
		response = await self.make_request(socket_path, cmd)
		if response and response.get_success():
			self.links = response.get_payload()
		else:
			self.general_logger.warning("Failed to get links")

	async def main(self):
		'''Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user'''
		# Try to get a set of links as soon as the monitor starts.
		await self.get_links()
		while not self.has_to_quit:
			self.whitelist, self.old_whitelist, self.old_whitelists = self.update_vars_from_file(
				self.old_whitelist, self.old_whitelists, [], True, *self.default_whitelists_file_path)
			self.blacklist, self.old_blacklist, self.old_blacklists = self.update_vars_from_file(
				self.old_blacklist, self.old_blacklists, [], True, *self.default_blacklists_file_path)
			self.webhooks, self.old_webhooks, self.old_webhooks_file = self.update_vars_from_file(
				self.old_webhooks, self.old_webhooks_file, {}, True, *self.default_webhooks_file_path)
			self.config, self.old_config, self.old_configs_file = self.update_vars_from_file(
				self.old_config, self.old_configs_file, {}, True, *self.default_configs_file_path)
			if self.new_links:
				self.general_logger.debug(f"Received new set of links: {self.new_links}")
				self.links = self.new_links
				self.new_links = []
			if self.buffer_links:
				self.general_logger.debug(f"Adding new set of links: {self.buffer_links}")
				self.links += self.buffer_links
				self.buffer_links = []
			try:
				await self.loop()
				self.shoe_check()
				self.shoe_manager.update_db()
			except:
				self.general_logger.exception("")
				data = {"content": f"{self.general_logger.name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."}
				await self.t_async_client.fetch(CRASH_WEBHOOK, method="POST", body=json.dumps(data), headers={"content-type": "application/json"})
			self.general_logger.info(f"Loop ended. Waiting {self.delay} secs.")
			await asyncio.sleep(self.delay)

	async def loop(self):
		'''User-defined loop. Replace this with a function that will be run every `delay` seconds'''
		await asyncio.sleep(1)

	def shoe_check(self):
		'''This is run just after the user-defined loop. It compares the just found shoes with the ones in the db.\n
			Any changed shoe is sent to the webhooks.\n
			You probably want to override this function to set custom embeds.'''
		for shoe in self.shoes:
			returned = self.set_reason_and_update_shoe(shoe)
			if returned:
				embed = discord_embeds.get_default_embed(returned)
				self.webhook_manager.add_to_queue(embed, self.webhooks)
		self.shoes = []

	def set_reason_and_update_shoe(self, shoe: Shoe) -> Optional[Shoe]:
		"""Check shoe against db. If present in db check if there are new sizes;\n
			if so, set reason to restock, update the db and return a shoe with only the restocked sizes;\n
			else update the shoe and return None. If not in the db return a copy of the shoe."""
		self.general_logger.debug(
			"Checking " + shoe.name + " - " + shoe.link + " in db...")
		new_or_restocked = True
		db_shoe = self.shoe_manager.find_shoe(shoe)
		return_shoe = copy.copy(shoe)
		self.general_logger.info("Checking " + shoe.link + " in db.")
		if db_shoe:
			new_or_restocked = False
			return_shoe.sizes = {}
			self.general_logger.debug("\tIt's present in db. Checking sizes.")
			self.general_logger.debug("\t\tdb_shoe sizes: " + str(db_shoe.sizes))
			self.general_logger.debug("\t\tShoe sizes: " + str(shoe.sizes))
			for shoe_size in shoe.sizes:
				try:
					db_available = db_shoe.sizes[shoe_size]["available"]
					if db_available != shoe.sizes[shoe_size]["available"]:
						if shoe.sizes[shoe_size]["available"] == True:
							new_or_restocked = True
							return_shoe.sizes[shoe_size] = shoe.sizes[shoe_size]
							self.general_logger.info("\t" + shoe.link + ": " +
                                                            str(shoe_size) + " is now available")
				except (NameError, KeyError):
					# is shoe size available?
					if shoe.sizes[shoe_size]["available"]:
						new_or_restocked = True
						return_shoe.sizes[shoe_size] = shoe.sizes[shoe_size]
						self.general_logger.info("\t" + shoe.link + ": " +
                                                    str(shoe_size) + " not in db.")

			if new_or_restocked:
				shoe.reason = shoe_stuff.RESTOCK
				return_shoe.reason = shoe_stuff.RESTOCK
				self.shoe_manager.update_shoe(shoe)
			else:
				self.general_logger.info("\t" + shoe.link + ": it has no restocked sizes.")
				self.shoe_manager.update_shoe(shoe, move_to_top=False)
				return None

		else:
			shoe.reason = shoe_stuff.NEW_RELEASE
			return_shoe.reason = shoe_stuff.NEW_RELEASE
			self.general_logger.info("\t" + shoe.link + ": not in db. Adding it.")
			self.shoe_manager.add_shoe(shoe)

		return return_shoe


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="BaseMonitor is the base monitor class from which every monitor should inherit. It provides a default loop which does nothing and is therefore fully executable.")
	default_delay = 5
	parser.add_argument("-d", "--delay", default=default_delay, type=int,
	                    help=f"Specify a delay for the loop. (default: {default_delay})")
	parser.add_argument("--output", action=argparse.BooleanOptionalAction,
                     default=True,
	                    help="Specify wether you want output to the console or not.",)
	args = parser.parse_args()
	if args.delay < 0:
		print(f"Cannot have a negative delay")
	BaseMonitor(args.output).start(args.delay)
