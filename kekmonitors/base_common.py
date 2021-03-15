import asyncio
import copy
import json
import os
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional

import __main__
import discord
import pymongo
from pymongo.collection import Collection
from watchdog import observers
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from kekmonitors.config import COMMANDS, ERRORS, Config, LogConfig
from kekmonitors.utils.server.msg import Cmd, Response, badResponse, okResponse
from kekmonitors.utils.server.server import Server
from kekmonitors.utils.shoe_manager import ShoeManager
from kekmonitors.utils.shoe_stuff import Shoe
from kekmonitors.utils.tools import get_file_if_exist_else_create, get_logger


def register_as(_type: str, name: str, path: str, client: Collection):
    path = os.path.abspath(path)
    existing = client[_type].find_one({"name": name})
    if not existing:
        client[_type].insert_one({"name": name, "path": path})
    else:
        if existing["path"] != path:
            raise Exception(
                f"Trying to register new {_type} ({name}) when it already exists in the database with a different path: {existing['path']}"
            )


class Common(Server, FileSystemEventHandler):
    def __init__(self, config: Config, **kwargs):
        self.class_name = self.get_class_name()

        self.config = config
        self.kwargs = kwargs
        log_config = LogConfig(config)

        log_config["OtherConfig"]["name"] += ".General"
        self.general_logger = get_logger(log_config)
        log_config["OtherConfig"]["name"] = (
            self.config["OtherConfig"]["name"] + ".Client"
        )
        self.client_logger = get_logger(log_config)

        self.delay = int(config["Options"]["loop_delay"])

        super().__init__(
            config,
            os.path.sep.join(
                [
                    self.config["GlobalConfig"]["socket_path"],
                    config["OtherConfig"]["name"],
                ]
            ),
        )

        self.register_db = pymongo.MongoClient(self.config["GlobalConfig"]["db_path"])[
            self.config["GlobalConfig"]["db_name"]
        ]["register"]

        self._loop_lock = asyncio.Lock()

        self.cmd_to_callback[COMMANDS.GET_WHITELIST] = self.on_get_whitelist
        self.cmd_to_callback[COMMANDS.GET_BLACKLIST] = self.on_get_blacklist
        self.cmd_to_callback[COMMANDS.GET_WEBHOOKS] = self.on_get_webhooks
        self.cmd_to_callback[COMMANDS.GET_CONFIG] = self.on_get_config
        self.cmd_to_callback[COMMANDS.GET_SHOES] = self.on_get_shoes

        is_monitor = config["OtherConfig"]["name"].startswith("Monitor.")
        self.is_monitor = is_monitor
        pre_conf_path = self.config["GlobalConfig"]["config_path"]
        specific_whitelist_json_filepath = os.path.sep.join(
            [pre_conf_path, "monitors" if is_monitor else "scrapers", "whitelists.json"]
        )
        specific_blacklist_json_filepath = os.path.sep.join(
            [pre_conf_path, "monitors" if is_monitor else "scrapers", "blacklists.json"]
        )
        specific_webhooks_json_filepath = os.path.sep.join(
            [pre_conf_path, "monitors" if is_monitor else "scrapers", "webhooks.json"]
        )
        specific_config_json_filepath = os.path.sep.join(
            [pre_conf_path, "monitors" if is_monitor else "scrapers", "configs.json"]
        )
        common_whitelist_json_filepath = os.path.sep.join(
            (pre_conf_path, "common", "whitelists.json")
        )
        common_blacklist_json_filepath = os.path.sep.join(
            (pre_conf_path, "common", "blacklists.json")
        )
        common_webhooks_json_filepath = os.path.sep.join(
            (pre_conf_path, "common", "webhooks.json")
        )
        common_config_json_filepath = os.path.sep.join(
            (pre_conf_path, "common", "configs.json")
        )

        self.specific_whitelist_json = self.load_config(
            specific_whitelist_json_filepath, []
        )  # type: List[str]
        self.common_whitelist_json = self.load_config(
            common_whitelist_json_filepath, []
        )  # type: List[str]
        self.specific_blacklist_json = self.load_config(
            specific_blacklist_json_filepath, []
        )  # type: List[str]
        self.common_blacklist_json = self.load_config(
            common_blacklist_json_filepath, []
        )  # type: List[str]
        self.specific_webhooks_json = self.load_config(
            common_webhooks_json_filepath, {}
        )  # type: Dict[str, Any]
        self.common_webhooks_json = self.load_config(
            specific_webhooks_json_filepath, {}
        )  # type: Dict[str, Any]
        self.specific_config_json = self.load_config(
            common_config_json_filepath, {}
        )  # type: Dict[str, Any]
        self.common_config_json = self.load_config(
            specific_config_json_filepath, {}
        )  # type: Dict[str, Any]

        self.whitelist_json = self.specific_whitelist_json + self.common_whitelist_json
        self.blacklist_json = self.specific_blacklist_json + self.common_blacklist_json
        self.webhooks_json = copy.copy(self.common_webhooks_json)
        self.webhooks_json.update(self.specific_webhooks_json)
        self.config_json = copy.copy(self.common_config_json)
        self.config_json.update(self.specific_config_json)

        self._new_specific_whitelist = None  # type: Optional[List[str]]
        self._new_specific_blacklist = None  # type: Optional[List[str]]
        self._new_specific_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
        self._new_specific_config = None  # type: Optional[Dict[str, Any]]

        self._new_common_whitelist = None  # type: Optional[List[str]]
        self._new_common_blacklist = None  # type: Optional[List[str]]
        self._new_common_webhooks = None  # type: Optional[Dict[str, Dict[str, Any]]]
        self._new_common_config = None  # type: Optional[Dict[str, Any]]

        self._has_to_quit = False
        self.shoe_manager = ShoeManager(config)
        self.register()

        if config["Options"]["disable_config_watcher"] == "False":
            observer = observers.Observer()
            observer.schedule(
                self,
                os.path.sep.join(
                    (
                        pre_conf_path,
                        "monitors" if self.is_monitor else "scrapers",
                    )
                ),
                True,
            )
            observer.schedule(self, os.path.sep.join((pre_conf_path, "common")), True)
            observer.start()

    def init(self, **kwargs):
        """Override this in your website-specific monitor, if needed."""
        pass

    async def async_init(self):
        """Override this in your website-specific monitor, if needed."""
        pass

    def on_shutdown(self):
        """Override this in your website-specific monitor, if needed."""
        pass

    async def on_async_shutdown(self):
        """Override this in your website-specific monitor, if needed."""
        pass

    def get_class_name(self):
        """Internal function used to get the correct filename."""
        """Not necessary, but sometimes you might want to override this."""
        return type(self).__name__

    def register(self):
        if self.is_monitor:
            register_as(
                "monitors", self.class_name, __main__.__file__, self.register_db
            )
        else:
            register_as(
                "scrapers", self.class_name, __main__.__file__, self.register_db
            )

    def on_modified(self, event: FileSystemEvent):
        # called when any of the monitored files is modified.
        # we are only interested int the configs for now.
        filepath = event.key[1]  # type: str

        # if a config file is updated:
        if not filepath.endswith(".json"):
            return
        if filepath.startswith(os.path.sep.join((self.config["GlobalConfig"]["config_path"], "common"))):
            asyncio.run_coroutine_threadsafe(
                self.update_common_configs(filepath), self._asyncio_loop
            )
        else:
            asyncio.run_coroutine_threadsafe(
                self.update_specific_configs(filepath), self._asyncio_loop
            )

    def on_any_event(self, event):
        return super().on_any_event(event)

    async def update_specific_configs(self, filepath: str):
        """Reads the provided config file and updates the variables"""
        self.general_logger.debug(f"File {filepath} has changed!")
        try:
            with open(filepath, "r") as f:
                j = json.load(f)
        except JSONDecodeError:
            self.general_logger.warning(
                f"File {filepath} has changed but contains invalid json data"
            )
            return

        splits = filepath.split(os.path.sep)

        # if it's from the monitors folder:
        if self.class_name in j:
            # we are interested in configs, whitelists, blacklists, webhooks
            if splits[-1] == "whitelists.json":
                self._new_specific_whitelist = j[self.class_name]
            elif splits[-1] == "configs.json":
                self._new_specific_config = j[self.class_name]
            elif splits[-1] == "blacklists.json":
                self._new_specific_blacklist = j[self.class_name]
            elif splits[-1] == "webhooks.json":
                self._new_specific_webhooks = j[self.class_name]
            else:
                return

        else:
            self.general_logger.debug("File not useful.")
            return

    async def update_common_configs(self, filepath: str):
        """Reads the provided config file and updates the variables"""
        self.general_logger.debug(f"File {filepath} has changed!")
        try:
            with open(filepath, "r") as f:
                j = json.load(f)
        except JSONDecodeError:
            self.general_logger.warning(
                f"File {filepath} has changed but contains invalid json data"
            )
            return

        splits = filepath.split(os.path.sep)

        # if it's from the monitors folder:
        if self.class_name in j:
            # we are interested in configs, whitelists, blacklists, webhooks
            if splits[-1] == "whitelists.json":
                self._new_common_whitelist = j[self.class_name]
            elif splits[-1] == "configs.json":
                self._new_common_config = j[self.class_name]
            elif splits[-1] == "blacklists.json":
                self._new_common_blacklist = j[self.class_name]
            elif splits[-1] == "webhooks.json":
                self._new_common_webhooks = j[self.class_name]
            else:
                return

        else:
            self.general_logger.debug("File not useful.")
            return

    def load_config(self, path, default_value):
        content = get_file_if_exist_else_create(path, "{}")
        try:
            j = json.loads(content)
        except JSONDecodeError:
            self.general_logger.exception(f"{path} is not valid json. Quitting.")
            exit(1)
        if self.class_name not in j:
            self.general_logger.warning(
                f"{self.class_name} not in {path}, continuing with empty entry."
            )
            return default_value
        else:
            return j[self.class_name]

    def update_config(self) -> List[str]:
        changed = []
        if self._new_common_blacklist is not None or self._new_specific_blacklist is not None:
            changed.append("blacklist")
            if self._new_common_blacklist is not None:
                self.common_blacklist_json = self._new_common_blacklist
            if self._new_specific_blacklist is not None:
                self.specific_blacklist_json = self._new_specific_blacklist
            self.blacklist_json = self.common_blacklist_json + self.specific_blacklist_json
            self.general_logger.info(f"New blacklist: {self.blacklist_json}")
            self._new_common_blacklist = self._new_specific_blacklist = None
        if self._new_common_whitelist is not None or self._new_specific_whitelist is not None:
            changed.append("whitelist")
            if self._new_common_whitelist is not None:
                self.common_whitelist_json = self._new_common_whitelist
            if self._new_specific_whitelist is not None:
                self.specific_whitelist_json = self._new_specific_whitelist
            self.whitelist_json = self.common_whitelist_json + self.specific_whitelist_json
            self.general_logger.info(f"New whitelist: {self.whitelist_json}")
            self._new_common_whitelist = self._new_specific_whitelist = None
        if self._new_common_webhooks is not None or self._new_specific_webhooks is not None:
            changed.append("webhooks")
            if self._new_common_webhooks is not None:
                self.common_webhooks_json = self._new_common_webhooks
            if self._new_specific_webhooks is not None:
                self.specific_webhooks_json = self._new_specific_webhooks
            self.webhooks_json = copy.copy(self.common_webhooks_json)
            self.webhooks_json.update(self.specific_webhooks_json)
            self.general_logger.info(f"New webhooks: {self.webhooks_json}")
            self._new_common_webhooks = self._new_specific_webhooks = None
        if self._new_common_config is not None or self._new_specific_config is not None:
            changed.append("config")
            if self._new_common_config is not None:
                self.common_config_json = self._new_common_config
            if self._new_specific_config is not None:
                self.specific_config_json = self._new_specific_config
            self.config_json = copy.copy(self.common_config_json)
            self.config_json.update(self.specific_config_json)
            self.general_logger.info(f"New config: {self.config_json}")
            self._new_common_config = self._new_specific_config = None
        return changed

    async def on_get_config(self, cmd: Cmd) -> Response:
        r = okResponse()
        r.payload = self.config_json
        return r

    async def on_get_whitelist(self, cmd: Cmd) -> Response:
        r = okResponse()
        r.payload = self.whitelist_json
        return r

    async def on_get_blacklist(self, cmd: Cmd) -> Response:
        r = okResponse()
        r.payload = self.blacklist_json
        return r

    async def on_get_webhooks(self, cmd: Cmd) -> Response:
        r = okResponse()
        r.payload = self.webhooks_json
        return r

    async def on_get_shoes(self, cmd: Cmd) -> Response:
        response = okResponse()
        response.payload = [shoe.__dict__ for shoe in self.shoes]
        return response

    def get_embed(self, shoe: Shoe) -> discord.Embed:
        return discord.Embed()

    async def main(self):
        pass

    def start(self):
        """Call this to start the loop."""
        self.init(**self.kwargs)
        self._main_task = self._asyncio_loop.create_task(self.main())
        self._asyncio_loop.run_forever()
        self.general_logger.debug("Shutting down...")
