import json
import time
from datetime import datetime
from queue import Queue
from threading import Event, Thread
from typing import Any, Dict, List, Tuple

import requests
from discord import Embed

from kekmonitors.config import Config, LogConfig
from kekmonitors.utils.tools import get_logger


class WebhookSender(Thread):
    """This handles sending embeds to one specific webhook. Obviously being a thread sub-class you should not add too many webhooks (in the order of the hundreds) for the same monitor.\n
    You should not use this directly, but `WebhookManager` instead"""

    def __init__(self, webhook: str, logconfig: LogConfig):
        self.config = logconfig
        self.webhook = webhook
        self.logger = get_logger(logconfig)
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
                self.add_event.clear()
                break
            while not self.queue.empty():
                webhook_values, embed, now = self.queue.get()
                if "custom" in webhook_values:
                    provider = webhook_values["custom"].get(
                        "provider", self.config["WebhookConfig"]["provider"]
                    )
                    timestamp_format = webhook_values["custom"].get(
                        "timestamp_format",
                        self.config["WebhookConfig"]["timestamp_format"],
                    )
                    ts = now.strftime(timestamp_format)
                    icon_url = webhook_values["custom"].get(
                        "icon_url", self.config["WebhookConfig"]["provider_icon"]
                    )
                    color = webhook_values["custom"].get(
                        "color", int(self.config["WebhookConfig"]["embed_color"])
                    )

                    embed.set_footer(text=" | ".join([provider, ts]), icon_url=icon_url)
                    embed.color = color
                else:
                    ts = now.strftime(self.config["WebhookConfig"]["timestamp_format"])

                    embed.set_footer(
                        text=f"{self.config['WebhookConfig']['provider']} | {ts}",
                        icon_url=self.config["WebhookConfig"]["provider_icon"],
                    )
                    embed.color = int(self.config["WebhookConfig"]["embed_color"])

                embed.timestamp = Embed.Empty
                data = {"embeds": [embed.to_dict()]}

                if "custom" in webhook_values:
                    if "avatar_image" in webhook_values["custom"]:
                        data["avatar_url"] = webhook_values["custom"]["avatar_image"]

                data = json.dumps(data)

                while True:
                    r = requests.post(
                        self.webhook,
                        data=data,
                        headers={"Content-Type": "application/json"},
                        timeout=3,
                    )
                    self.logger.debug(
                        f"Posted to {self.webhook} with code {r.status_code}"
                    )
                    if "x-rateLimit-remaining" in r.headers:
                        remaining_requests = r.headers["x-rateLimit-remaining"]
                        if remaining_requests == "0":
                            delay = int(r.headers["x-rateLimit-reset-after"])
                            self.logger.debug(
                                f"No available requests reminaing for {self.webhook}, waiting {str(delay)} secs"
                            )
                            time.sleep(delay)
                            continue
                        if r.status_code == 429:
                            delay = int(r.headers["x-rateLimit-reset-after"])
                            self.logger.debug(
                                f"Got 429 for {self.webhook}, waiting {str(delay)} secs"
                            )
                            time.sleep(delay)
                            continue
                    else:
                        self.logger.warning(
                            f"Attention: {self.webhook} posted with {r.status_code} but it doesnt contain the rateLimit header; are you sure the webhook is correct???"
                        )
                    break
            self.add_event.clear()


class WebhookManager:
    def __init__(self, config: Config):
        logconfig = LogConfig(config)
        self.config = logconfig
        logconfig["OtherConfig"]["socket_name"] += ".WebhookManager"
        self.logger = get_logger(logconfig)
        self.webhook_senders = {}  # type: Dict[str, WebhookSender]
        self.add_event = Event()
        self.logger.debug("Started webhook manager")

    def quit(self):
        self.logger.debug("Starting shutdown...")
        for w in self.webhook_senders:
            ws = self.webhook_senders[w]
            self.logger.debug(f"Waiting {ws.webhook}...")
            while not ws.is_done():
                time.sleep(0.5)
            self.logger.debug(f"Stopping {ws.webhook}...")
            ws.quit()

        for w in self.webhook_senders:
            ws = self.webhook_senders[w]
            self.logger.debug(f"Cleaning up {ws.webhook}...")
            ws.join()
        self.logger.debug("Shut down...")

    def add_to_queue(self, embed: Embed, webhooks: Dict[str, Dict[str, Any]]):
        """Add the embed to the queue of webhooks to send. It will be processed as soon as possible."""
        for webhook in webhooks:
            if webhook in self.webhook_senders:
                self.webhook_senders[webhook].add_to_queue(webhooks[webhook], embed)
            else:
                self.webhook_senders[webhook] = WebhookSender(webhook, self.config)
                self.webhook_senders[webhook].start()
                self.webhook_senders[webhook].add_to_queue(webhooks[webhook], embed)
