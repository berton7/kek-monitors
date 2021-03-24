import asyncio
import json
import traceback
from datetime import datetime

import discord

from kekmonitors import discord_embeds
from kekmonitors.base_common import Common
from kekmonitors.comms.msg import Cmd, Response, okResponse
from kekmonitors.comms.server import Server
from kekmonitors.config import COMMANDS, Config
from kekmonitors.shoe_stuff import Shoe
from kekmonitors.utils.network_utils import NetworkUtils
from kekmonitors.webhook_manager import WebhookManager


class BaseScraper(Common, NetworkUtils):
    def __init__(self, config: Config = Config(), **kwargs):
        config["OtherConfig"]["socket_name"] = f"Scraper.{self.get_class_name()}"

        super().__init__(config, **kwargs)
        super(Server, self).__init__(config["OtherConfig"]["socket_name"])

        self.cmd_to_callback[COMMANDS.PING] = self._on_ping
        self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving
        self.crash_webhook = config["WebhookConfig"]["crash_webhook"]
        self.webhook_manager = WebhookManager(config)

    def get_embed(self, shoe: Shoe) -> discord.Embed:
        return discord_embeds.get_scraper_embed(shoe)

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

    async def main(self):
        """Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user"""
        await self.async_init()
        while True:
            async with self._loop_lock:
                changed = self.update_config()
                if changed:
                    await self.on_config_change(changed)
                try:
                    await self.loop()
                except:
                    self.general_logger.exception("")
                    if self.crash_webhook:
                        data = {
                            "content": f"{self.class_name} has crashed:\n{traceback.format_exc()}\nRestarting in {self.delay} secs."
                        }
                        await self.client.fetch(
                            self.crash_webhook,
                            method="POST",
                            body=json.dumps(data),
                            headers={"content-type": "application/json"},
                            raise_error=False,
                        )
                self.general_logger.info(f"Loop ended, waiting {self.delay} secs")
            await asyncio.sleep(self.delay)

    async def loop(self):
        """User-defined loop. Replace this with a function that will be run every `delay` seconds"""
        await asyncio.sleep(1)

    def shoe_check(self, shoe: Shoe, update_ts=True):
        """Searches the database for the given, updating it if found or adding it if not found. Also updates the last_seen timestamp.

        Args:
            shoe (Shoe): Shoe to check
        """
        if update_ts:
            shoe.last_seen = datetime.utcnow().timestamp()
        if self.shoe_manager.find_shoe({"link": shoe.link}):
            self.shoe_manager._db.find_one_and_update(
                {"_Shoe__link": shoe.link},
                {"$set": {"_Shoe__last_seen": shoe.last_seen}},
            )
        else:
            self.shoe_manager.add_shoe(shoe)
            if self.config["Options"]["enable_webhooks"] == "True":
                self.webhook_manager.add_to_queue(
                    self.get_embed(shoe), self.webhooks_json
                )

    async def _on_ping(self, cmd: Cmd) -> Response:
        return okResponse()
