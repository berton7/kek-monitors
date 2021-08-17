import asyncio
import json
import traceback
from datetime import datetime
from typing import List

import discord

from kekmonitors import discord_embeds
from kekmonitors.base_common import Common
from kekmonitors.comms.msg import Cmd, Response, okResponse
from kekmonitors.comms.server import Server
from kekmonitors.config import COMMANDS, Config
from kekmonitors.shoe_stuff import Shoe
from kekmonitors.utils.network_utils import NetworkUtils
from kekmonitors.webhook_manager import WebhookManager


class BasePriceMonitor(Common, NetworkUtils):
    def __init__(self, config: Config = None, **kwargs):
        if not config:
            config = Config()
        config["OtherConfig"]["socket_name"] = f"Monitor.{self.get_class_name()}"

        super().__init__(config, **kwargs)
        super(Server, self).__init__(config["OtherConfig"]["socket_name"])

        self.cmd_to_callback[COMMANDS.PING] = self._on_ping
        self.cmd_to_callback[COMMANDS.STOP] = self._stop_serving

        self.crash_webhook = config["WebhookConfig"]["crash_webhook"]
        self.webhook_manager = WebhookManager(config)

        self._cur_shoes = [] # type: List[Shoe]

    def get_embed(self, shoe: Shoe) -> discord.Embed:
        return discord_embeds.get_default_embed(shoe)

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

    async def main(self):
        """Main loop. Updates configs, runs user-defined loop and performs links/shoes updates for the user"""
        await self.async_init()
        while True:
            async with self._loop_lock:
                changed = self.update_config()
                if changed:
                    await self.on_config_change(changed)
                self._cur_shoes.clear()
                try:
                    await self.loop()
                except:
                    self.general_logger.exception("")
                    if self.crash_webhook:
                        content = f"```{traceback.format_exc()}\n\nRestarting in {self.delay} seconds.```"
                        if len(content) > 2000:
                            content = f"```Stacktrace too long -- please view logs.\n\nRestarting in {self.delay} seconds.```"
                        data = json.dumps(
                            {
                                "content": content,
                                "username": f"Monitor {self.class_name}",
                                "avatar_url": self.config["WebhookConfig"][
                                    "provider_icon"
                                ],
                            }
                        )
                        await self.client.fetch(
                            self.crash_webhook,
                            method="POST",
                            body=data,
                            headers={"content-type": "application/json"},
                            raise_error=False,
                        )
                self._update_db()
                self.general_logger.info(f"Loop ended. Waiting {self.delay} secs.")
            await asyncio.sleep(self.delay)

    async def loop(self):
        """User-defined loop. Replace this with a function that will be run every `delay` seconds"""
        await asyncio.sleep(1)

    def store_shoe(self, shoe: Shoe):
        self._cur_shoes.append(shoe)

    def shoe_check(self, shoe: Shoe, update_ts=True):
        if update_ts:
            shoe.last_seen = datetime.utcnow().timestamp()

        returned = None
        db_shoe = self.shoe_manager.find_shoe({"_Shoe__link": shoe.link})
        if db_shoe:
            if db_shoe.price != shoe.price:
                self.general_logger.debug(f"Shoe {shoe.name} has different price from last time ({db_shoe.price} => {shoe.price})")
                returned = shoe
        else:
            self.general_logger.debug(f"New shoe {shoe.name} with price {shoe.price}")
            returned = shoe

        if returned and self.config["Options"]["enable_webhooks"] == "True":
            embed = self.get_embed(returned)
            self.webhook_manager.add_to_queue(embed, self.webhooks_json)

    def _update_db(self):
        self.shoe_manager._db.drop()
        if self._cur_shoes:
            self.shoe_manager.add_shoes(self._cur_shoes)