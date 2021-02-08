import json
import time
from datetime import datetime
from logging import Logger
from queue import Queue
from threading import Event, Thread
from typing import Any, Dict, List, Tuple

import requests
from discord import Embed
from kekmonitors.config import Config, LogConfig
from kekmonitors.utils.tools import get_logger


class WebhookSender(Thread):
	'''This handles sending embeds to one specific webhook. Obviously being a thread sub-class you should not add too many webhooks (in the order of the hundreds) for the same monitor.\n
	You should not use this directly, but `WebhookManager` instead'''

	def __init__(self, webhook: str, config: Config):
		self.config = config
		self.webhook = webhook
		self.logger = Logger(self.config.name)
		self.queue = Queue()  # type: Queue[Tuple[List[Any], List[Any], datetime]]
		# contains the webhook config, embeds and time at which they were added
		self.add_event = Event()
		self.has_to_quit = False
		super().__init__()

	def add_to_queue(self, webhook_values: Any, embed: Embed):
		now = datetime.now()
		self.queue.put((webhook_values, embed, now))
		self.add_event.set()

	def is_done(self) -> bool:
		return not self.add_event.isSet()

	def quit(self):
		self.has_to_quit = True
		self.add_event.set()

	def run(self):
		while True:
			self.add_event.wait()
			if self.has_to_quit:
				break
			while not self.queue.empty():
				webhook_values, embed, now = self.queue.get()
				if "custom" in webhook_values:
					provider = webhook_values["custom"].get(
						"provider", self.config.provider)
					timestamp_format = webhook_values["custom"].get(
						"timestamp_format", self.config.timestamp_format)
					ts = now.strftime(timestamp_format)
					icon_url = webhook_values["custom"].get(
						"icon_url", self.self.config.provider_icon)
					color = webhook_values["custom"].get(
						"color", self.self.config.embed_color)

					embed.set_footer(text=" | ".join([provider, ts]), icon_url=icon_url)
					embed.color = color
				else:
					ts = now.strftime(self.config.timestamp_format)

					embed.set_footer(text=f"{self.config.provider} | {ts}",
					                 icon_url=self.self.config.provider_icon)
					embed.color = self.self.config.embed_color

				embed.timestamp = Embed.Empty
				data = {"embeds": [embed.to_dict()]}

				if "custom" in webhook_values:
					if "avatar_image" in webhook_values["custom"]:
						data["avatar_url"] = webhook_values["custom"]["avatar_image"]

				data = json.dumps(data)

				while True:
					r = requests.post(self.webhook, data=data, headers={
					                  "Content-Type": "application/json"}, timeout=3)
					self.logger.debug(f"Posted to {self.webhook} with code {r.status_code}")
					remaining_requests = r.headers["x-rateLimit-remaining"]
					if remaining_requests == "0":
						delay = int(r.headers["x-rateLimit-reset-after"])
						self.logger.debug(
							f"No available requests reminaing for {self.webhook}, waiting {delay} secs")
						time.sleep(delay)
					if r.status_code == 429:
						delay = r.headers["x-rateLimit-reset-after"]
						self.logger.debug(f"Got 429 for {self.webhook}, waiting {delay} secs")
						time.sleep(delay)
						continue
					break
			self.add_event.clear()


class WebhookManager():
	def __init__(self, config: Config):
		self.config = config
		logconfig = LogConfig(self.config)
		logconfig.name += ".WebhookManager"
		self.logger = get_logger(logconfig)
		self.webhook_senders = {}  # type: Dict[str, WebhookSender]
		self.add_event = Event()
		self.logger.debug("Started webhook manager")

	def quit(self):
		self.logger.debug("Starting shutdown...")
		for w in self.webhook_senders:
			ws = self.webhook_senders[w]
			while not ws.is_done():
				time.sleep(0.5)
			ws.quit()

		for w in self.webhook_senders:
			ws = self.webhook_senders[w]
			ws.join()
		self.logger.debug("Shut down...")

	def add_to_queue(self, embed: Embed, webhooks: Dict[str, Dict[str, Any]]):
		'''Add the embed to the queue of webhooks to send. It will be processed as soon as possible.'''
		for webhook in webhooks:
			if webhook in self.webhook_senders:
				self.webhook_senders[webhook].add_to_queue(webhooks[webhook], embed)
			else:
				self.webhook_senders[webhook] = WebhookSender(webhook, self.config)
				self.webhook_senders[webhook].start()
				self.webhook_senders[webhook].add_to_queue(webhooks[webhook], embed)
