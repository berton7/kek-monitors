import asyncio
import copy
import json
import traceback
from typing import List

import pymongo

from kekmonitors.base_common import Common
from kekmonitors.config import COMMANDS, Config
from kekmonitors.utils.discord_embeds import get_scraper_embed
from kekmonitors.utils.network_utils import NetworkUtils
from kekmonitors.utils.server.msg import Cmd, Message, Response, okResponse
from kekmonitors.utils.server.server import Server
from kekmonitors.utils.shoe_stuff import Shoe
from kekmonitors.utils.tools import dump_error
from kekmonitors.utils.webhook_manager import WebhookManager


class BaseScraper(Common, NetworkUtils):
	def __init__(self, config: Config = Config(), **kwargs):
		config['OtherConfig']['name'] = f"Scraper.{self.get_class_name()}"

		super().__init__(config, **kwargs)
		super(Server, self).__init__(config['OtherConfig']['name'])

		self.cmd_to_callback[COMMANDS.PING] = self._on_ping
		self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving
		self.cmd_to_callback[COMMANDS.GET_SHOES] = self.on_get_shoes
		self.links = []  # type: List[str]
		self.shoes = []  # type: List[Shoe]
		self._previous_links = []  # type: List[Shoe]
		self._previous_shoes = []  # type: List[Shoe]
		self.crash_webhook = config['WebhookConfig']['crash_webhook']
		self.shoes_db = pymongo.MongoClient(
			config['GlobalConfig']['db_path'])[config['GlobalConfig']['db_name']]["links"][self.class_name]
		self.webhook_manager = WebhookManager(config)

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

	async def on_get_shoes(self, cmd: Cmd) -> Message:
		response = okResponse()
		response.payload = [shoe.__dict__ for shoe in self.shoes]
		return response

	async def main(self):
		'''Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user'''
		await self.async_init()
		while True:
			async with self._loop_lock:
				self.update_local_config()
				try:
					await self.loop()
					await self.update_links()
				except:
					self.general_logger.exception("")
					if self.crash_webhook:
						data = {"content": f"{self.class_name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."}
						await self.client.fetch(self.crash_webhook, method="POST", body=json.dumps(data), headers={"content-type": "application/json"}, raise_error=False)
				self.general_logger.info(f"Loop ended, waiting {self.delay} secs")
			await asyncio.sleep(self.delay)

	async def loop(self):
		'''User-defined loop. Replace this with a function that will be run every `delay` seconds'''
		'''Modify self.links in order to force a link update on the corresponding monitor.'''
		await asyncio.sleep(1)

	async def update_links(self):
		'''This is called just after self.loop. Checks if any of the links have been modified and sends them to the corresponding monitor.'''
		if self.shoes != self._previous_shoes:
			for shoe in self.shoes:
				if not self.shoe_manager.find_shoe({"link": shoe.link}):
					self.shoe_manager.add_shoe(shoe)
					if self.config["Options"]["enable_webhooks"] == "True":
						self.webhook_manager.add_to_queue(
							get_scraper_embed(shoe), self.webhooks_json)
			await self._set_shoes()
			self._previous_shoes = copy.copy(self.shoes)  # allows to perform ==

	async def _on_ping(self, cmd: Cmd) -> Response:
		return okResponse()

	async def _set_shoes(self):
		'''Connect to the corresponding monitor, if available, and tell it to set the new links.'''
		socket_path = f"{self.config['GlobalConfig']['socket_path']}/Monitor.{self.class_name}"
		cmd = Cmd()
		cmd.cmd = COMMANDS.SET_SHOES
		cmd.payload = [shoe.__dict__ for shoe in self.shoes]
		response = await self.make_request(socket_path, cmd)
		if response.error.value:
			dump_error(self.client_logger, response)

	async def _add_shoes(self):
		'''Connect to the corresponding monitor, if available, and send it the new links.'''
		socket_path = f"{self.config['GlobalConfig']['socket_path']}/Monitor.{self.class_name}"
		cmd = Cmd()
		cmd.cmd = COMMANDS.ADD_SHOES
		cmd.payload = [shoe.__dict__ for shoe in self.shoes]
		response = await self.make_request(socket_path, cmd)
		if response.error.value:
			dump_error(self.client_logger, response)
