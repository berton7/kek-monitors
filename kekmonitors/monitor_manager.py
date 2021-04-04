import asyncio
import copy
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, cast

import pymongo
import tornado.httpclient
from watchdog import observers
from watchdog.events import FileSystemEvent, FileSystemEventHandler

import kekmonitors.utils.tools
from kekmonitors.comms.msg import Cmd, Response, badResponse, okResponse
from kekmonitors.comms.server import Server
from kekmonitors.config import COMMANDS, ERRORS, Config, LogConfig
from kekmonitors.discord_embeds import get_mm_crash_embed

if sys.version_info[1] > 6:
    import uvloop


def get_parent_directory(src: str) -> str:
    """
    Return the parent directory of `src`
    """
    return src[: src.rfind(os.path.sep)]


class MonitorManager(Server, FileSystemEventHandler):
    """This can be used to manage monitors/scrapers with an external api."""

    def __init__(self, config: Config = None):
        if not config:
            config = Config()
        # set default name if not already set in config
        if not config["OtherConfig"]["socket_name"]:
            config["OtherConfig"]["socket_name"] = f"Executable.MonitorManager"

        self.config = config

        # create logger
        logconfig = LogConfig(config)
        logconfig["OtherConfig"]["socket_name"] += ".General"
        self.general_logger = kekmonitors.utils.tools.get_logger(logconfig)

        if sys.version_info[1] > 6:
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        else:
            self.general_logger.warning(
                f"You're currently running python {sys.version_info[0]}.{sys.version_info[1]}, which does not support uvloop. Please consider upgrading to at least 3.7, since uvloop brings many enhancements to the asyncio loop."
            )

        super().__init__(
            config, f"{self.config['GlobalConfig']['socket_path']}/MonitorManager"
        )  # Server init
        super(Server).__init__()  # FileSystemEventHandler init

        # initialize callbacks
        self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR_MANAGER] = self._stop_serving
        self.cmd_to_callback[COMMANDS.MM_ADD_MONITOR] = self.on_add_monitor
        self.cmd_to_callback[COMMANDS.MM_ADD_SCRAPER] = self.on_add_scraper
        self.cmd_to_callback[
            COMMANDS.MM_ADD_MONITOR_SCRAPER
        ] = self.on_add_monitor_scraper
        self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR] = self.on_stop_monitor
        self.cmd_to_callback[COMMANDS.MM_STOP_SCRAPER] = self.on_stop_scraper
        self.cmd_to_callback[
            COMMANDS.MM_STOP_MONITOR_SCRAPER
        ] = self.on_stop_monitor_scraper
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_STATUS
        ] = self.on_get_monitor_status
        self.cmd_to_callback[
            COMMANDS.MM_GET_SCRAPER_STATUS
        ] = self.on_get_scraper_status
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_SCRAPER_STATUS
        ] = self.on_get_status
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_CONFIG
        ] = self.on_get_monitor_config
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_CONFIG
        ] = self.on_set_monitor_config
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_WHITELIST
        ] = self.on_get_monitor_whitelist
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_WHITELIST
        ] = self.on_set_monitor_whitelist
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_BLACKLIST
        ] = self.on_get_monitor_blacklist
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_BLACKLIST
        ] = self.on_set_monitor_blacklist
        self.cmd_to_callback[
            COMMANDS.MM_GET_MONITOR_WEBHOOKS
        ] = self.on_get_monitor_webhooks
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_WEBHOOKS
        ] = self.on_set_monitor_webhooks
        self.cmd_to_callback[
            COMMANDS.MM_GET_SCRAPER_CONFIG
        ] = self.on_get_scraper_config
        self.cmd_to_callback[
            COMMANDS.MM_SET_SCRAPER_CONFIG
        ] = self.on_set_scraper_config
        self.cmd_to_callback[
            COMMANDS.MM_GET_SCRAPER_WHITELIST
        ] = self.on_get_scraper_whitelist
        self.cmd_to_callback[
            COMMANDS.MM_SET_SCRAPER_WHITELIST
        ] = self.on_set_scraper_whitelist
        self.cmd_to_callback[
            COMMANDS.MM_GET_SCRAPER_BLACKLIST
        ] = self.on_get_scraper_blacklist
        self.cmd_to_callback[
            COMMANDS.MM_SET_SCRAPER_BLACKLIST
        ] = self.on_set_scraper_blacklist
        self.cmd_to_callback[
            COMMANDS.MM_GET_SCRAPER_WEBHOOKS
        ] = self.on_get_scraper_webhooks
        self.cmd_to_callback[
            COMMANDS.MM_SET_SCRAPER_WEBHOOKS
        ] = self.on_set_scraper_webhooks
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_SCRAPER_BLACKLIST
        ] = self.on_set_monitor_scraper_blacklist
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_SCRAPER_WHITELIST
        ] = self.on_set_monitor_scraper_whitelist
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_SCRAPER_WEBHOOKS
        ] = self.on_set_monitor_scraper_webhooks
        self.cmd_to_callback[
            COMMANDS.MM_SET_MONITOR_SCRAPER_CONFIG
        ] = self.on_set_monitor_scraper_configs
        self.cmd_to_callback[COMMANDS.MM_GET_SCRAPER_SHOES] = self.on_get_scraper_shoes
        self.cmd_to_callback[COMMANDS.MM_GET_MONITOR_SHOES] = self.on_get_monitor_shoes

        # initialize variables
        self.monitor_processes = {}  # type: Dict[str, Dict[str, Any]]
        self.scraper_processes = {}  # type: Dict[str, Dict[str, Any]]
        self.monitor_sockets = {}  # type: Dict[str, str]
        self.scraper_sockets = {}  # type: Dict[str, str]
        self.register_db = pymongo.MongoClient(
            self.config["GlobalConfig"]["db_path"]
        )[  # database where to find class_name -> filename relation
            self.config["GlobalConfig"]["db_name"]
        ][
            "register"
        ]

        # let's avoid concurrency problems on socket creation/deletion
        self.socket_lock = asyncio.Lock()
        # and don't stop on MM_STOP_MONITOR_MANAGER if we are in the loop
        self._loop_lock = asyncio.Lock()

        # mandatory arguments, needed in the command
        self.add_args = ["name"]
        self.stop_args = ["name"]
        self.getter_args = ["name"]
        self.setter_args = ["name", "payload"]

        self.shutdown_all_on_exit = True  # you might wanna change this

        # needed for the crash webhook
        tornado.httpclient.AsyncHTTPClient.configure(
            "tornado.curl_httpclient.CurlAsyncHTTPClient"
        )
        self.client = tornado.httpclient.AsyncHTTPClient()

        # create main loop task
        self.check_status_task = self._asyncio_loop.create_task(self.check_status())

        # watches the config folder for any change. calls on_modified when any monitored file is modified
        self.watcher = observers.Observer()
        self.watcher.schedule(self, self.config["GlobalConfig"]["config_path"], True)
        self.watcher.schedule(self, self.config["GlobalConfig"]["socket_path"], True)

        # needed for proper shutdown
        self.has_to_quit = False

    def start(self):
        """Start the Monitor Manager."""
        self.watcher.start()
        self._asyncio_loop.run_forever()

    def on_modified(self, event: FileSystemEvent):
        # called when any of the monitored files is modified.
        # we are only interested int the configs for now.
        filepath = event.key[1]  # type: str

        if not filepath.endswith(".json"):
            return
        # if a config file is updated:
        if filepath.startswith(self.config["GlobalConfig"]["config_path"]):
            if filepath.startswith(
                os.path.sep.join((self.config["GlobalConfig"]["config_path"], "common"))
            ):
                asyncio.run_coroutine_threadsafe(
                    self.update_common_config(filepath), self._asyncio_loop
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    self.update_specific_config(filepath), self._asyncio_loop
                )

    def on_created(self, event: FileSystemEvent):
        filename = event.key[1]  # type: str

        # if a socket was created:
        if filename.find(self.config["GlobalConfig"]["socket_path"]) != -1:
            asyncio.run_coroutine_threadsafe(self.on_add_sockets(), self._asyncio_loop)

    def on_deleted(self, event):
        filename = event.key[1]  # type: str

        # if a socket was deleted:
        if filename.find(self.config["GlobalConfig"]["socket_path"]) != -1:
            asyncio.run_coroutine_threadsafe(
                self.on_delete_sockets(), self._asyncio_loop
            )

    async def on_add_sockets(self):
        """
        Routine that updates the internal list of available sockets on add event
        """
        async with self.socket_lock:
            # get any socket that is not in the list
            new_monitor_sockets = {}  # type: Dict[str, str]
            new_scraper_sockets = {}  # type: Dict[str, str]
            for filename in os.listdir(self.config["GlobalConfig"]["socket_path"]):
                splits = filename.split(".")
                if splits[0] == "Monitor" and splits[1] not in self.monitor_sockets:
                    new_monitor_sockets[splits[1]] = os.path.sep.join(
                        [self.config["GlobalConfig"]["socket_path"], filename]
                    )
                elif splits[0] == "Scraper" and splits[1] not in self.scraper_sockets:
                    new_scraper_sockets[splits[1]] = os.path.sep.join(
                        [self.config["GlobalConfig"]["socket_path"], filename]
                    )

            # check if it's alive
            alive_monitor_sockets, alive_scraper_sockets = await asyncio.gather(
                self.get_alive_sockets(new_monitor_sockets.values()),
                self.get_alive_sockets(new_scraper_sockets.values()),
            )

            # if it is, add it to the list
            for class_name in new_monitor_sockets:
                if new_monitor_sockets[class_name] in alive_monitor_sockets:
                    self.monitor_sockets[class_name] = new_monitor_sockets[class_name]

            for class_name in new_scraper_sockets:
                if new_scraper_sockets[class_name] in alive_scraper_sockets:
                    self.scraper_sockets[class_name] = new_scraper_sockets[class_name]

    async def on_delete_sockets(self):
        """
        Routine that updates the internal list of available sockets on delete event
        """
        async with self.socket_lock:
            existing_monitor_sockets = []
            existing_scraper_sockets = []
            # get the current list of existing sockets
            for f in list(os.listdir(self.config["GlobalConfig"]["socket_path"])):
                if f.startswith("Monitor."):
                    existing_monitor_sockets.append(f)
                elif f.startswith("Scraper."):
                    existing_scraper_sockets.append(f)

            # temp copy
            updated_monitor_sockets = copy.copy(self.monitor_sockets)
            updated_scraper_sockets = copy.copy(self.scraper_sockets)

            # remove every internal socket that is not existing
            for class_name in self.monitor_sockets:
                if "Monitor." + class_name not in existing_monitor_sockets:
                    updated_monitor_sockets.pop(class_name)
            for class_name in self.scraper_sockets:
                if "Scraper." + class_name not in existing_scraper_sockets:
                    updated_scraper_sockets.pop(class_name)

            self.monitor_sockets = updated_monitor_sockets
            self.scraper_sockets = updated_scraper_sockets

    async def get_alive_sockets(self, sockets: List[str]) -> List[str]:
        """
        Ping the provided sockets and return a list of alive sockets
        """
        tasks = []
        for socket in sockets:
            cmd = Cmd()
            cmd.cmd = COMMANDS.PING
            tasks.append(self.make_request(socket, cmd))

        responses = await asyncio.gather(*tasks)  # type: List[Response]
        alive = []
        for response, socket in zip(responses, sockets):
            if not response.error.value:
                alive.append(socket)

        return alive

    async def update_common_config(self, filename: str):
        """Reads the provided config file and updates the interested monitors/scrapers"""
        self.general_logger.debug(f"File {filename} has changed!")
        try:
            with open(filename, "r") as f:
                j = json.load(f)
        except JSONDecodeError:
            self.general_logger.warning(
                f"File {filename} has changed but contains invalid json data"
            )
            return

        splits = filename.split(os.path.sep)

        for sockets in (self.monitor_sockets, self.scraper_sockets):
            commands = []  # List[Cmd]
            sock_paths = []  # type: List[str]

            # we are interested in configs, whitelists, blacklists, webhooks
            if splits[-1] == "whitelists.json":
                cmd = COMMANDS.SET_COMMON_WHITELIST
            elif splits[-1] == "configs.json":
                cmd = COMMANDS.SET_COMMON_CONFIG
            elif splits[-1] == "blacklists.json":
                cmd = COMMANDS.SET_COMMON_BLACKLIST
            elif splits[-1] == "webhooks.json":
                cmd = COMMANDS.SET_COMMON_WEBHOOKS
            else:
                return

            # for every monitor socket
            for name in sockets:
                if name in j:
                    sock_path = sockets[name]
                    c = Cmd()
                    c.cmd = cmd
                    # send only the corresponding part to the monitor
                    c.payload = j[name]
                    commands.append(c)
                    sock_paths.append(sock_path)

            # prepare to make all the async requests
            tasks = []
            for sock_path, command in zip(sock_paths, commands):
                tasks.append(self.make_request(sock_path, command))

            # send the requests
            responses = await asyncio.gather(*tasks)  # List[Response]

            for response in responses:
                if response.error.value:
                    self.general_logger.warning(
                        f"Failed to update config: {response.error}"
                    )

    async def update_specific_config(self, filename: str):
        """Reads the provided config file and updates the interested monitors/scrapers"""
        self.general_logger.debug(f"File {filename} has changed!")
        try:
            with open(filename, "r") as f:
                j = json.load(f)
        except JSONDecodeError:
            self.general_logger.warning(
                f"File {filename} has changed but contains invalid json data"
            )
            return

        splits = filename.split(os.path.sep)
        commands = []  # List[Cmd]
        sock_paths = []  # type: List[str]

        # if it's from the monitors folder:
        if "monitors" in filename.split(os.path.sep):
            sockets = self.monitor_sockets
        elif "scrapers" in filename.split(os.path.sep):
            sockets = self.scraper_sockets
        else:
            self.general_logger.debug("File not useful.")
            return

        # we are interested in configs, whitelists, blacklists, webhooks
        if splits[-1] == "whitelists.json":
            cmd = COMMANDS.SET_SPECIFIC_WHITELIST
        elif splits[-1] == "configs.json":
            cmd = COMMANDS.SET_SPECIFIC_CONFIG
        elif splits[-1] == "blacklists.json":
            cmd = COMMANDS.SET_SPECIFIC_BLACKLIST
        elif splits[-1] == "webhooks.json":
            cmd = COMMANDS.SET_SPECIFIC_WEBHOOKS
        else:
            return

        # for every monitor socket
        for name in sockets:
            if name in j:
                sock_path = sockets[name]
                c = Cmd()
                c.cmd = cmd
                # send only the corresponding part to the monitor
                c.payload = j[name]
                commands.append(c)
                sock_paths.append(sock_path)

        # prepare to make all the async requests
        tasks = []
        for sock_path, command in zip(sock_paths, commands):
            tasks.append(self.make_request(sock_path, command))

        # send the requests
        responses = await asyncio.gather(*tasks)  # List[Response]

        for response in responses:
            if response.error.value:
                self.general_logger.warning(
                    f"Failed to update config: {response.error}"
                )

    async def on_server_stop(self):
        """
        Routine that runs on server stop. Shuts down the monitor manager
        """
        async with self._loop_lock:
            # stop the config watcher
            self.watcher.stop()
            self.watcher.join()

            if self.shutdown_all_on_exit:
                # get all the existing sockets
                sockets = []  # type: List[str]
                tasks = []
                for sockname in os.listdir(self.config["GlobalConfig"]["socket_path"]):
                    if sockname.startswith("Scraper.") or sockname.startswith(
                        "Monitor."
                    ):
                        cmd = Cmd()
                        cmd.cmd = COMMANDS.STOP
                        sockets.append(sockname)
                        self.general_logger.info(f"Stopping {sockname}...")
                        tasks.append(
                            self.make_request(
                                f"{self.config['GlobalConfig']['socket_path']}{os.path.sep}{sockname}",
                                cmd,
                            )
                        )

                # send request to stop
                responses = await asyncio.gather(*tasks)  # type: List[Response]

                for sockname, r in zip(sockets, responses):
                    # if an error happened...
                    if r.error.value:
                        # if the socket was not used remove it
                        if r.error == ERRORS.SOCKET_COULDNT_CONNECT:
                            os.remove(
                                os.path.sep.join(
                                    [
                                        self.config["GlobalConfig"]["socket_path"],
                                        sockname,
                                    ]
                                )
                            )
                            self.general_logger.info(
                                f"{self.config['GlobalConfig']['socket_path']}{os.path.sep}{sockname} was removed because unavailable"
                            )
                        # else something else happened, dont do anything
                        else:
                            self.general_logger.warning(
                                f"Error occurred while attempting to stop {sockname}: {r.error}"
                            )
                    # ok
                    else:
                        self.general_logger.info(f"{sockname} was successfully stopped")

        self._asyncio_loop.stop()
        self.general_logger.info("Shutting down...")
        return okResponse()

    async def check_status(self):
        """Main MonitorManager loop. Every second it checks its monitored processes and looks if they are still alive, possibly reporting any exit code"""
        while True:
            async with self._loop_lock:
                new_monitor_processes = {}
                for class_name in self.monitor_processes:
                    monitor = self.monitor_processes[class_name]["process"]
                    if monitor.poll() is not None:
                        log = f"Monitor {class_name} has stopped with code: {monitor.returncode}"
                        if monitor.returncode:
                            self.general_logger.warning(log)
                            if self.config["WebhookConfig"]["crash_webhook"]:
                                embed = get_mm_crash_embed(
                                    "Monitor " + class_name,
                                    monitor.returncode,
                                    monitor.pid,
                                )
                                ts = datetime.now().strftime(
                                    self.config["WebhookConfig"]["timestamp_format"]
                                )

                                embed.set_footer(
                                    text=f"{self.config['WebhookConfig']['provider']} | {ts}",
                                    icon_url=self.config["WebhookConfig"][
                                        "provider_icon"
                                    ],
                                )
                                data = json.dumps(
                                    {
                                        "embeds": [embed.to_dict()],
                                        "username": "MonitorManager process watcher",
                                        "avatar_url": self.config["WebhookConfig"][
                                            "provider_icon"
                                        ],
                                    }
                                )
                                r = await self.client.fetch(
                                    self.config["WebhookConfig"]["crash_webhook"],
                                    method="POST",
                                    body=data,
                                    headers={"content-type": "application/json"},
                                    raise_error=False,
                                )
                        else:
                            self.general_logger.info(log)
                    else:
                        new_monitor_processes[class_name] = self.monitor_processes[
                            class_name
                        ]
                self.monitor_processes = new_monitor_processes

                new_scraper_processes = {}
                for class_name in self.scraper_processes:
                    scraper = self.scraper_processes[class_name]["process"]
                    if scraper.poll() is not None:
                        log = f"Scraper {class_name} has stopped with code: {scraper.returncode}"
                        if scraper.returncode:
                            self.general_logger.warning(log)
                            if self.config["WebhookConfig"]["crash_webhook"]:
                                embed = get_mm_crash_embed(
                                    "Scraper " + class_name,
                                    scraper.returncode,
                                    scraper.pid,
                                )
                                ts = datetime.now().strftime(
                                    self.config["WebhookConfig"]["timestamp_format"]
                                )

                                embed.set_footer(
                                    text=f"{self.config['WebhookConfig']['provider']} | {ts}",
                                    icon_url=self.config["WebhookConfig"][
                                        "provider_icon"
                                    ],
                                )
                                data = json.dumps(
                                    {
                                        "embeds": [embed.to_dict()],
                                        "username": "MonitorManager process watcher",
                                        "avatar_url": self.config["WebhookConfig"][
                                            "provider_icon"
                                        ],
                                    }
                                )
                                r = await self.client.fetch(
                                    self.config["WebhookConfig"]["crash_webhook"],
                                    method="POST",
                                    body=data,
                                    headers={"content-type": "application/json"},
                                    raise_error=False,
                                )
                        else:
                            self.general_logger.info(log)
                    else:
                        new_scraper_processes[class_name] = self.scraper_processes[
                            class_name
                        ]
                self.scraper_processes = new_scraper_processes
            await asyncio.sleep(1)

    async def on_add_monitor(self, cmd: Cmd) -> Response:
        r = badResponse()
        success, missing = cmd.has_valid_args(self.add_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            db_monitor = self.register_db["monitors"].find_one(
                {"name": payload["name"]}
            )
            if db_monitor:
                success, reason = await self.add_monitor(db_monitor["path"], payload)
                if success:
                    r = okResponse()
                else:
                    r.error = ERRORS.MM_COULDNT_ADD_MONITOR
                    r.info = reason
            else:
                r.error = ERRORS.MONITOR_NOT_REGISTERED
                r.info = f"Tried to add monitor {payload['name']} but it was not found in the db. Did you start it at least once manually?"
        else:
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"Missing arguments: {missing}"
        return r

    async def on_add_scraper(self, cmd: Cmd) -> Response:
        r = badResponse()
        success, missing = cmd.has_valid_args(self.add_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            db_scraper = self.register_db["scrapers"].find_one(
                {"name": payload["name"]}
            )
            if db_scraper:
                success, reason = await self.add_scraper(db_scraper["path"], payload)
                if success:
                    r = okResponse()
                else:
                    r.error = ERRORS.MM_COULDNT_ADD_SCRAPER
                    r.info = reason
            else:
                r.error = ERRORS.SCRAPER_NOT_REGISTERED
                r.info = f"Tried to add scraper {payload['name']} but it was not found in the db. Did you start it at least once manually?"
        else:
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"Missing arguments: {missing}"

        return r

    async def on_add_monitor_scraper(self, cmd: Cmd) -> Response:
        r = Response()
        cmd1 = cmd
        cmd2 = copy.copy(cmd)
        cmd2.payload = copy.deepcopy(cmd1.payload)
        r1, r2 = await asyncio.gather(
            self.on_add_monitor(cmd1), self.on_add_scraper(cmd2)
        )
        r.error = (
            ERRORS.OK
            if not r1.error.value and not r2.error.value
            else ERRORS.MM_COULDNT_ADD_MONITOR_SCRAPER
        )
        r.info = f"Monitor: {r1.error.name}, Scraper: {r2.error.name}"
        if r.error.value and r.error:
            self.general_logger.warning(f"Couldn't add monitor and scraper")
            kekmonitors.utils.tools.dump_error(self.general_logger, r)

        return r

    async def on_stop_monitor(self, cmd: Cmd) -> Response:
        r = badResponse()
        success, missing = cmd.has_valid_args(self.stop_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            socket = f"{self.config['GlobalConfig']['socket_path']}/Monitor.{payload['name']}"
            command = Cmd()
            command.cmd = COMMANDS.STOP
            self.general_logger.debug(f"Sending STOP to {socket}...")
            r = await self.make_request(socket, command)
            self.general_logger.debug(f"Sent STOP to {socket}")
        else:
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"Missing arguments: {missing}"
        return r

    async def on_stop_scraper(self, cmd: Cmd) -> Response:
        r = badResponse()
        success, missing = cmd.has_valid_args(self.stop_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            socket = f"{self.config['GlobalConfig']['socket_path']}/Scraper.{payload['name']}"
            command = Cmd()
            command.cmd = COMMANDS.STOP
            self.general_logger.debug(f"Sending STOP to {socket}...")
            r = await self.make_request(socket, command)
            self.general_logger.debug(f"Sent STOP to {socket}")
        else:
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"Missing arguments: {missing}"
        return r

    async def on_stop_monitor_scraper(self, cmd: Cmd) -> Response:
        r = badResponse()
        success, missing = cmd.has_valid_args(self.stop_args)
        if success:
            r1, r2 = await asyncio.gather(
                self.on_stop_monitor(cmd), self.on_stop_scraper(cmd)
            )
            r.error = (
                ERRORS.OK
                if not r1.error.value and not r2.error.value
                else ERRORS.MM_COULDNT_STOP_MONITOR_SCRAPER
            )
            r.info = f"Monitor: {r1.error.name}, Scraper: {r2.error.name}"
            if r.error.value and r.error:
                self.general_logger.warning(f"Couldn't stop monitor and scraper")
                kekmonitors.utils.tools.dump_error(self.general_logger, r)
        else:
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"Missing arguments: {missing}"
        return r

    async def on_get_monitor_status(self, cmd: Cmd) -> Response:
        process_status = {}
        for class_name in self.monitor_processes:
            start = self.monitor_processes[class_name]["start"].strftime(
                "%m/%d/%Y, %H:%M:%S"
            )
            process_status[class_name] = {
                "Started at": start,
                "PID": self.monitor_processes[class_name]["process"].pid,
            }
        sockets_status = {}
        # for class_name in self.monitor_sockets:
        # sockets_status[class_name] = {class_name: self.monitor_sockets[class_name]}
        sockets_status = self.monitor_sockets
        response = okResponse()
        response.payload = {
            "monitored_processes": process_status,
            "available_sockets": sockets_status,
        }
        return response

    async def on_get_scraper_status(self, cmd: Cmd) -> Response:
        process_status = {}
        for class_name in self.scraper_processes:
            start = self.scraper_processes[class_name]["start"].strftime(
                "%m/%d/%Y, %H:%M:%S"
            )
            process_status[class_name] = {
                "Started at": start,
                "PID": self.scraper_processes[class_name]["process"].pid,
            }
        sockets_status = {}
        # for class_name in self.scraper_sockets:
        # sockets_status[class_name] = {class_name: self.scraper_sockets[class_name]}
        sockets_status = self.scraper_sockets
        response = okResponse()
        response.payload = {
            "monitored_processes": process_status,
            "available_sockets": sockets_status,
        }
        return response

    async def on_get_status(self, cmd: Cmd) -> Response:
        ms = await self.on_get_monitor_status(cmd)
        ss = await self.on_get_scraper_status(cmd)
        response = okResponse()
        msp = cast(Dict[str, Any], ms.payload)  # type: Dict[str, Any]
        ssp = cast(Dict[str, Any], ss.payload)  # type: Dict[str, Any]
        response.payload = {"monitors": msp, "scrapers": ssp}
        return response

    async def add_monitor(self, filename: str, kwargs: Dict[str, str]):
        class_name = kwargs.pop("name")

        if class_name in self.monitor_processes:
            self.general_logger.debug(
                f"Tried to add an already existing monitor ({class_name} ({filename}))"
            )
            return False, "Monitor already started."

        first_part_cmd = (
            f"nohup {sys.executable} {filename} --no-output --no-config-watcher"
        )

        args = []
        for key in kwargs:
            args.append(f"--{key} {kwargs[key]}")

        cmd = " ".join((first_part_cmd, *args))

        self.general_logger.debug(f"Starting {class_name} ({filename})...")
        monitor = subprocess.Popen(
            shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        await asyncio.sleep(2)  # wait to check if process is still alive

        if monitor.poll() is not None:
            success = False
            msg = f"Failed to start monitor {class_name} ({filename})"
            self.general_logger.warning(
                f"Tried to start {class_name} ({filename}) but failed"
            )
        else:
            self.general_logger.info(
                f"Added monitor {class_name} with pid {monitor.pid}"
            )
            self.monitor_processes[class_name] = {
                "process": monitor,
                "start": datetime.now(),
            }
            success = True
            msg = ""
        return success, msg

    async def add_scraper(self, filename: str, kwargs: Dict[str, str]):
        class_name = kwargs.pop("name")

        if class_name in self.scraper_processes:
            self.general_logger.debug(
                f"Tried to add an already existing scraper ({class_name} ({filename}))"
            )
            return False, "Scraper already started."

        first_part_cmd = (
            f"nohup {sys.executable} {filename} --no-output --no-config-watcher"
        )

        args = []
        for key in kwargs:
            args.append(f"--{key} {kwargs[key]}")

        cmd = " ".join((first_part_cmd, " ".join(args)))

        self.general_logger.debug(f"Starting {class_name} ({filename})...")
        scraper = subprocess.Popen(
            shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        await asyncio.sleep(2)  # wait to check if process is still alive

        if scraper.poll() is not None:
            success = False
            msg = f"Failed to start scraper {class_name} ({filename})"
            self.general_logger.warning(
                f"Tried to start {class_name} ({filename}) but failed"
            )
        else:
            self.general_logger.info(
                f"Added scraper {class_name} with pid {scraper.pid}"
            )
            self.scraper_processes[class_name] = {
                "process": scraper,
                "start": datetime.now(),
            }
            success = True
            msg = ""
        return success, msg

    async def on_get_monitor_config(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_CONFIG, True)

    async def on_set_monitor_config(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "configs.json", True)

    async def on_get_monitor_whitelist(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_WHITELIST, True)

    async def on_set_monitor_whitelist(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "whitelists.json", True)

    async def on_get_monitor_blacklist(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_BLACKLIST, True)

    async def on_set_monitor_blacklist(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "blacklists.json", True)

    async def on_get_monitor_webhooks(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_WEBHOOKS, True)

    async def on_set_monitor_webhooks(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "webhooks.json", True)

    async def on_get_scraper_config(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_CONFIG, False)

    async def on_set_scraper_config(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "configs.json", False)

    async def on_get_scraper_whitelist(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_WHITELIST, False)

    async def on_set_scraper_whitelist(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "whitelists.json", False)

    async def on_get_scraper_blacklist(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_BLACKLIST, False)

    async def on_set_scraper_blacklist(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "blacklists.json", False)

    async def on_get_scraper_webhooks(self, cmd: Cmd) -> Response:
        return await self.specific_config_getter(cmd, COMMANDS.GET_WEBHOOKS, False)

    async def on_set_scraper_webhooks(self, cmd: Cmd) -> Response:
        return await self.specific_config_setter(cmd, "webhooks.json", False)

    async def on_set_monitor_scraper_blacklist(self, cmd: Cmd) -> Response:
        return await self.common_config_setter(cmd, "blacklists.json")

    async def on_set_monitor_scraper_whitelist(self, cmd: Cmd) -> Response:
        return await self.common_config_setter(cmd, "whitelists.json")

    async def on_set_monitor_scraper_webhooks(self, cmd: Cmd) -> Response:
        return await self.common_config_setter(cmd, "webhooks.json")

    async def on_set_monitor_scraper_configs(self, cmd: Cmd) -> Response:
        return await self.common_config_setter(cmd, "configs.json")

    async def specific_config_getter(
        self, cmd: Cmd, command: COMMANDS, is_monitor: bool
    ):
        success, missing = cmd.has_valid_args(self.getter_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            c = Cmd()
            c.cmd = command
            r = await self.make_request(
                f"{self.config['GlobalConfig']['socket_path']}/{'Monitor' if is_monitor else 'Scraper'}.{payload['name']}",
                c,
            )
            return r
        else:
            r = badResponse()
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"{missing}"
            return r

    async def specific_config_setter(self, cmd: Cmd, filename: str, is_monitor: bool):
        success, missing = cmd.has_valid_args(self.setter_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            cp = os.path.sep.join(
                (
                    self.config["GlobalConfig"]["config_path"],
                    "monitors" if is_monitor else "scrapers",
                    filename,
                )
            )
            with open(
                cp,
                "r",
            ) as rf:
                f = json.load(rf)
            f[payload["name"]] = payload["payload"]
            with open(
                cp,
                "w",
            ) as wf:
                json.dump(f, wf)
        else:
            r = badResponse()
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"{missing}"
            return r

    async def common_config_setter(self, cmd: Cmd, filename: str):
        success, missing = cmd.has_valid_args(self.setter_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            cp = os.path.sep.join(
                (self.config["GlobalConfig"]["config_path"], "common", filename)
            )
            with open(
                cp,
                "r",
            ) as rf:
                f = json.load(rf)
            f[payload["name"]] = payload["payload"]
            with open(
                cp,
                "w",
            ) as wf:
                json.dump(f, wf)
        else:
            r = badResponse()
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"{missing}"
            return r

    async def on_get_scraper_shoes(self, cmd: Cmd) -> Response:
        success, missing = cmd.has_valid_args(self.getter_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            c = Cmd()
            c.cmd = COMMANDS.GET_SHOES
            r = await self.make_request(
                f"{self.config['GlobalConfig']['socket_path']}/Monitor.{payload['name']}",
                c,
            )
            return r
        else:
            r = badResponse()
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"{missing}"
            return r

    async def on_get_monitor_shoes(self, cmd: Cmd) -> Response:
        success, missing = cmd.has_valid_args(self.getter_args)
        if success:
            payload = cast(Dict[str, Any], cmd.payload)
            c = Cmd()
            c.cmd = COMMANDS.SET_SHOES
            r = await self.make_request(
                f"{self.config['GlobalConfig']['socket_path']}/Monitor.{payload['name']}",
                c,
            )
            return r
        else:
            r = badResponse()
            r.error = ERRORS.MISSING_PAYLOAD_ARGS
            r.info = f"{missing}"
            return r


if __name__ == "__main__":
    MonitorManager().start()
