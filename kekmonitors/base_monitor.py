import asyncio
import copy
import json
import traceback
from typing import List, Optional

from kekmonitors.base_common import Common
from kekmonitors.config import COMMANDS, ERRORS, Config
from kekmonitors.utils import discord_embeds, shoe_stuff
from kekmonitors.utils.network_utils import NetworkUtils
from kekmonitors.utils.server.msg import Cmd, Response, badResponse, okResponse
from kekmonitors.utils.server.server import Server
from kekmonitors.utils.shoe_manager import ShoeManager
from kekmonitors.utils.shoe_stuff import Shoe
from kekmonitors.utils.tools import dump_error
from kekmonitors.utils.webhook_manager import WebhookManager


class BaseMonitor(Common, NetworkUtils):
	def __init__(self, config: Config = Config()):
		if not config.name:
			config.name = f"Monitor.{self.get_class_name()}"
		elif not config.name.startswith("Monitor."):
			raise Exception(
				f"You must start the monitor name with \"Monitor.\"! Currently: {config.name}")
		self.crash_webhook = config.crash_webhook

		super().__init__(config)
		super(Server, self).__init__(config.name)

		self._mark_as_monitor()

		self.cmd_to_callback[COMMANDS.PING] = self._on_ping
		self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving
		self.cmd_to_callback[COMMANDS.SET_LINKS] = self.on_set_links
		self.cmd_to_callback[COMMANDS.ADD_LINKS] = self.on_add_links

		self.buffer_links = []  # type: List[str]
		self.new_links = []  # type: List[str]
		self.links = []  # type: List[str]
		self.shoes = []  # type: List[Shoe]

		self.shoe_manager = ShoeManager()
		self.webhook_manager = WebhookManager(config)

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
		self.general_logger.debug("Waiting for loop to complete...")
		async with self._loop_lock:
			pass
		self.general_logger.debug("Loop is completed, starting shutdown...")
		await self.on_async_shutdown()
		self._asyncio_loop.stop()
		self.general_logger.debug("Shutting down webhook manager...")
		self.webhook_manager.quit()
		self.on_shutdown()
		return okResponse()

	async def _on_ping(self, cmd: Cmd) -> Response:
		return okResponse()

	async def _get_links(self):
		socket_path = f"{self.config.socket_path}/Scraper.{self.class_name}"
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
		await self.async_init()
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
					if self.crash_webhook:
						data = json.dumps(
							{"content": f"{self.class_name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."[:2000]})
						await self.client.fetch(self.crash_webhook, method="POST", body=data, headers={"content-type": "application/json"}, raise_error=False)
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
				self.webhook_manager.add_to_queue(embed, self.webhooks_json)

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
