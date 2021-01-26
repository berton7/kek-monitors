import argparse
import asyncio
import copy
import json
import os
import traceback
from typing import List, Optional

from configs.config import COMMANDS, ERRORS, SOCKET_PATH, WEBHOOK_CONFIG
from utils import discord_embeds, shoe_stuff
from utils.common_base import Common
from utils.network_utils import NetworkUtils
from utils.server.msg import *
from utils.server.server import Server
from utils.shoe_manager import ShoeManager
from utils.shoe_stuff import Shoe
from utils.tools import dump_error
from utils.webhook_manager import WebhookManager


class BaseMonitor(Common, NetworkUtils):
	def __init__(self, add_stream_handler: bool = True):
		# init some internal variables (logger, links)
		logger_name = f"Monitor.{self.get_class_name()}"

		super().__init__(
			logger_name, add_stream_handler, f"{SOCKET_PATH}/Monitor.{self.get_class_name()}")
		super(Server, self).__init__(logger_name)

		self.cmd_to_callback[COMMANDS.PING] = self._on_ping
		self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving
		self.cmd_to_callback[COMMANDS.SET_LINKS] = self.on_set_links
		self.cmd_to_callback[COMMANDS.ADD_LINKS] = self.on_add_links

		self.buffer_links = []  # type: List[str]
		self.new_links = []  # type: List[str]
		self.links = []  # type: List[str]
		self.shoes = []  # type: List[Shoe]

		self.shoe_manager = ShoeManager(logger=self.general_logger)
		self.webhook_manager = WebhookManager(
			self.general_logger.name, add_stream_handler)

		# website-specific variables should be declared here
		self.init()

	async def on_set_links(self, msg: Cmd) -> Response:
		response = badResponse()
		p = msg.payload
		if p is not None:
			if isinstance(p, list):
				self.new_links = p
				response.error = ERRORS.OK
			else:
				self.client_logger.warning(
					"Received new set of links, but payload was not a list: ", p)
				response.error = ERRORS.BAD_PAYLOAD
				response.info = f"Invalid links (expected list, got {type(p)}"

		else:
			self.client_logger.warning(
				"Missing payload; msg: ", msg.get_json())
			response.error = ERRORS.MISSING_PAYLOAD
		return response

	async def on_add_links(self, msg: Cmd) -> Response:
		response = badResponse()
		p = msg.payload
		if p is not None:
			if isinstance(p, list):
				self.buffer_links = p
				response.error = ERRORS.OK
			else:
				self.general_logger.warning(
					"Received new added links, but payload was not a list: ", p)
				response.error = ERRORS.BAD_PAYLOAD
				response.info = f"Invalid links (expected list, got {type(p)}"

		else:
			self.general_logger.warning(
				"Missing payload; msg: ", msg.get_json())
			response.error = ERRORS.MISSING_PAYLOAD
		return response

	async def on_server_stop(self) -> Response:
		async with self._loop_lock:
			self._asyncio_loop.stop()
		self.general_logger.debug("Shutting down webhook manager...")
		self.webhook_manager.quit()
		return okResponse()

	async def _on_ping(self, cmd: Cmd) -> Response:
		return okResponse()

	async def _get_links(self):
		socket_path = f"{SOCKET_PATH}/Scraper.{self.class_name}"
		self.client_logger.debug("Getting links...")

		cmd = Cmd()
		cmd.cmd = COMMANDS.GET_LINKS
		response = await self.make_request(socket_path, cmd)
		if not response.error.value:
			if response.payload:
				self.links = response.payload
			else:
				self.client_logger.warning("Tried to get links but payload was invalid.")
				dump_error(self.client_logger, response)
		else:
			self.client_logger.warning(f"Failed to get links")
			dump_error(self.client_logger, response)

	async def main(self):
		'''Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user'''
		# Try to get a set of links as soon as the monitor starts.
		await self._get_links()
		while True:
			async with self._loop_lock:
				self.update_local_config()
				if self.new_links:
					self.general_logger.info(f"Received new set of links: {self.new_links}")
					self.links = self.new_links
					self.new_links = []
				if self.buffer_links:
					self.general_logger.info(f"Adding new set of links: {self.buffer_links}")
					self.links += self.buffer_links
					self.buffer_links = []
				try:
					self.shoes = []
					await self.loop()
					self.shoe_check()
				except:
					self.general_logger.exception("")
					if WEBHOOK_CONFIG.CRASH_WEBHOOK:
						data = json.dumps(
							{"content": f"{self.class_name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."[:2000]})
						await self.client.fetch(WEBHOOK_CONFIG.CRASH_WEBHOOK, method="POST", body=data, headers={"content-type": "application/json"}, raise_error=False)
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

	def set_reason_and_update_shoe(self, shoe: Shoe) -> Optional[Shoe]:
		"""Check shoe against db. If present in db check if there are new sizes;\n
			if so, set reason to restock, update the db and return a shoe with only the restocked sizes;\n
			else update the shoe and return None. If not in the db return a copy of the shoe."""
		self.general_logger.debug(
			f"Checking {shoe.name} - {shoe.link} in db...")
		new_or_restocked = True
		db_shoe = self.shoe_manager.find_shoe({"link": shoe.link})
		return_shoe = copy.deepcopy(shoe)
		if db_shoe:
			new_or_restocked = False
			return_shoe.sizes = {}
			self.general_logger.debug("\tIt's present in db. Checking sizes.")
			self.general_logger.debug(f"\t\tdb_shoe sizes: {str(db_shoe.sizes)}")
			self.general_logger.debug(f"\t\tShoe sizes: {str(shoe.sizes)}")
			for shoe_size in shoe.sizes:
				try:
					db_available = db_shoe.sizes[shoe_size]["available"]
					if db_available != shoe.sizes[shoe_size]["available"]:
						if shoe.sizes[shoe_size]["available"] == True:
							new_or_restocked = True
							return_shoe.sizes[shoe_size] = shoe.sizes[shoe_size]
							self.general_logger.info(
								f"\t{shoe.link}: {str(shoe_size)} is now available")
				except (NameError, KeyError):
					# is shoe size available?
					if shoe.sizes[shoe_size]["available"]:
						new_or_restocked = True
						return_shoe.sizes[shoe_size] = shoe.sizes[shoe_size]
						self.general_logger.info(f"\t{shoe.link}: {str(shoe_size)} not in db.")

			if new_or_restocked:
				shoe.reason = shoe_stuff.RESTOCK
				return_shoe.reason = shoe_stuff.RESTOCK
				self.shoe_manager.update_shoe(shoe)
			else:
				self.general_logger.info(f"\t{shoe.link}: it has no restocked sizes.")
				self.shoe_manager.update_shoe(shoe)
				return None

		else:
			shoe.reason = shoe_stuff.NEW_RELEASE
			return_shoe.reason = shoe_stuff.NEW_RELEASE
			self.general_logger.info(f"\t{shoe.link}: not in db. Adding it.")
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
