import asyncio
import copy
import json
import traceback
from datetime import datetime
from typing import Optional

import discord

from kekmonitors import discord_embeds, shoe_stuff
from kekmonitors.base_common import Common
from kekmonitors.comms.msg import Cmd, Response, okResponse
from kekmonitors.comms.server import Server
from kekmonitors.config import COMMANDS, Config
from kekmonitors.shoe_stuff import Shoe
from kekmonitors.utils.network_utils import NetworkUtils
from kekmonitors.webhook_manager import WebhookManager


class BaseMonitor(Common, NetworkUtils):
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
                self.general_logger.info(f"Loop ended. Waiting {self.delay} secs.")
            await asyncio.sleep(self.delay)

    async def loop(self):
        """User-defined loop. Replace this with a function that will be run every `delay` seconds"""
        await asyncio.sleep(1)

    def shoe_check(self, shoe: Shoe, update_ts=True):
        if update_ts:
            shoe.last_seen = datetime.utcnow().timestamp()
        returned = self.set_reason_and_update_shoe(shoe)
        if returned and self.config["Options"]["enable_webhooks"] == "True":
            embed = self.get_embed(returned)
            self.webhook_manager.add_to_queue(embed, self.webhooks_json)

    def set_reason_and_update_shoe(self, shoe: Shoe) -> Optional[Shoe]:
        """Check shoe against db. If present in db check if there are new sizes;\n
        if so, set reason to restock, update the db and return a shoe with only the restocked sizes;\n
        else update the shoe and return None. If not in the db return a copy of the shoe."""
        self.general_logger.debug(f"Checking {shoe.name} - {shoe.link} in db...")
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
                                f"\t{shoe.link}: {str(shoe_size)} is now available"
                            )
                except (NameError, KeyError):
                    # is shoe size available?
                    if shoe.sizes[shoe_size]["available"]:
                        new_or_restocked = True
                        return_shoe.sizes[shoe_size] = shoe.sizes[shoe_size]
                        self.general_logger.info(
                            f"\t{shoe.link}: {str(shoe_size)} not in db."
                        )

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
