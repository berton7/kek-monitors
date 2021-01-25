import argparse
import asyncio
import copy
import json
import os
import traceback
from typing import List, Optional

from configs.config import COMMANDS, SOCKET_PATH, WEBHOOK_CONFIG
from utils.common_base import Common
from utils.network_utils import NetworkUtils
from utils.server.msg import Cmd, Message, Response, okResponse
from utils.server.server import Server


class BaseScraper(Common, NetworkUtils):
	def __init__(self, add_stream_handler: Optional[bool] = True):
		logger_name = f"Scraper.{self.get_class_name()}"

		super().__init__(
			logger_name, add_stream_handler, f"{SOCKET_PATH}/Scraper.{self.get_class_name()}")
		super(Server, self).__init__(logger_name)

		self.cmd_to_callback[COMMANDS.PING] = self._on_ping
		self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving
		self.cmd_to_callback[COMMANDS.SET_LINKS] = self.on_get_links
		self.links = []  # type: List[str]
		self._previous_links = []  # type: List[str]

		# website-specific variables should be declared here
		self.init()

	async def on_get_links(self, cmd: Cmd) -> Message:
		response = okResponse()
		response.payload = self.links
		return response

	async def on_server_stop(self):
		self._has_to_quit = True
		return okResponse()

	async def main(self):
		'''Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user'''
		while not self._has_to_quit:
			self.update_local_config()
			try:
				await self.loop()
				await self.update_links()
			except:
				self.general_logger.exception("")
				if WEBHOOK_CONFIG.CRASH_WEBHOOK:
					data = {"content": f"{self.class_name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."}
					await self.client.fetch(WEBHOOK_CONFIG.CRASH_WEBHOOK, method="POST", body=json.dumps(data), headers={"content-type": "application/json"}, raise_error=False)
			self.general_logger.info(f"Loop ended, waiting {self.delay} secs")
			await asyncio.sleep(self.delay)

		self.general_logger.info("Shutting down...")

	async def loop(self):
		'''User-defined loop. Replace this with a function that will be run every `delay` seconds'''
		'''Modify self.links in order to force a link update on the corresponding monitor.'''
		await asyncio.sleep(1)

	async def update_links(self):
		'''This is called just after self.loop. Checks if any of the links have been modified and sends them to the corresponding monitor.'''
		if self.links != self._previous_links:
			await self._set_links()
			self._previous_links = copy.deepcopy(self.links)

	async def _on_ping(self, cmd: Cmd) -> Response:
		return okResponse()

	async def _set_links(self):
		'''Connect to the corresponding monitor, if available, and tell it to set the new links.'''
		socket_path = f"{SOCKET_PATH}/Monitor.{self.class_name}"
		cmd = Cmd()
		cmd.cmd = COMMANDS.SET_LINKS
		cmd.payload = self.links
		response = await self.make_request(socket_path, cmd)
		if not response.success:
			self.client_logger.warning(
				f"_set_links: got bad response: {response.reason}")

	async def _add_links(self):
		'''Connect to the corresponding monitor, if available, and send it the new links.'''
		socket_path = f"{SOCKET_PATH}/Monitor.{self.class_name}"
		cmd = Cmd()
		cmd.cmd = COMMANDS.ADD_LINKS
		cmd.payload = self.links
		response = await self.make_request(socket_path, cmd)
		if not response.success:
			self.client_logger.warning(
				f"_add_links: got bad response: {response.reason}")


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="BaseScraper is the base scraper class from which every scraper should inherit. It provides a default loop which does nothing and is therefore fully executable.")
	default_delay = 5
	parser.add_argument("-d", "--delay", default=default_delay, type=int,
	                    help=f"Specify a delay for the loop. (default: {default_delay})")
	parser.add_argument("--output", action=argparse.BooleanOptionalAction,
                     default=True,
	                    help="Specify wether you want output to the console or not.",)
	args = parser.parse_args()
	if args.delay < 0:
		print(f"Cannot have a negative delay")
	BaseScraper(args.output).start(args.delay)
