import asyncio
import json
import os
import shlex
import subprocess
from datetime import datetime
from json.decoder import JSONDecodeError
from typing import Any, Dict, Optional, Union, cast

import tornado.httpclient
from watchdog import observers
from watchdog.events import FileSystemEvent, FileSystemEventHandler

import utils.tools
from configs.config import COMMANDS, SOCKET_PATH, WEBHOOK_CONFIG
from utils.server.msg import *
from utils.server.server import Server
import copy


def get_directory_from_file(src: str):
	return src[:src.rfind(os.path.sep)]


class MonitorManager(Server, FileSystemEventHandler):
	'''This can be used to manage monitors/scrapers with an external api.'''

	def __init__(self):
		logger_name = "Executable.MonitorManager"
		super().__init__(logger_name, True, f"{SOCKET_PATH}/MonitorManager")
		super(Server).__init__()
		self.general_logger = utils.tools.get_logger(logger_name + ".General")
		self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR_MANAGER] = self._stop_serving
		self.cmd_to_callback[COMMANDS.MM_ADD_MONITOR] = self.on_add_monitor
		self.cmd_to_callback[COMMANDS.MM_ADD_SCRAPER] = self.on_add_scraper
		self.cmd_to_callback[COMMANDS.MM_ADD_MONITOR_SCRAPER] = self.on_add_monitor_scraper
		self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR] = self.on_stop_monitor
		self.cmd_to_callback[COMMANDS.MM_STOP_SCRAPER] = self.on_stop_scraper
		self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR_SCRAPER] = self.on_stop_monitor_scraper
		self.cmd_to_callback[COMMANDS.MM_GET_MONITOR_STATUS] = self.on_get_monitor_status
		self.cmd_to_callback[COMMANDS.MM_GET_SCRAPER_STATUS] = self.on_get_scraper_status
		self.cmd_to_callback[COMMANDS.MM_GET_MONITOR_SCRAPER_STATUS] = self.on_get_status
		self.cmd_to_callback[COMMANDS.MM_GET_CONFIG] = self.on_get_config
		self.cmd_to_callback[COMMANDS.MM_SET_CONFIG] = self.on_set_config
		self.cmd_to_callback[COMMANDS.MM_GET_WHITELIST] = self.on_get_whitelist
		self.cmd_to_callback[COMMANDS.MM_SET_WHITELIST] = self.on_set_whitelist
		self.cmd_to_callback[COMMANDS.MM_GET_WEBHOOKS] = self.on_get_webhooks
		self.cmd_to_callback[COMMANDS.MM_SET_WEBHOOKS] = self.on_set_webhooks

		self.monitor_processes = {}  # type: Dict[str, Dict[str, Any]]
		self.scraper_processes = {}  # type: Dict[str, Dict[str, Any]]
		self.monitor_sockets = {}  # type: Dict[str, str]
		self.scraper_sockets = {}  # type: Dict[str, str]
		self.socket_lock = asyncio.Lock()

		# mandatory arguments, needed in the command
		self.add_scraper_args = self.add_monitor_args = self.add_monitor_scraper_args = [
			"filename", "class_name"]
		self.stop_args = ["class_name"]
		self.shutdown_all_on_exit = True   # you might wanna change this

		self._loop_lock = asyncio.Lock()
		tornado.httpclient.AsyncHTTPClient.configure(
			"tornado.curl_httpclient.CurlAsyncHTTPClient")
		self.client = tornado.httpclient.AsyncHTTPClient()

		# watches the config folder for any change. calls on_modified when any monitored file is modified
		self.config_watcher = observers.Observer()
		self.config_watcher.schedule(self, "./configs", True)
		self.config_watcher.schedule(self, SOCKET_PATH, True)
		self.has_to_quit = False

	def start(self):
		'''Start the Monitor Manager.'''
		self.config_watcher.start()
		self.check_status_task = self._asyncio_loop.create_task(self.check_status())
		self._asyncio_loop.run_forever()

	def on_modified(self, event: FileSystemEvent):
		# called when any of the monitored files is modified.
		# we are only interested int the configs for now.
		filename = event.key[1]  # type: str
		# if a config file is updated:
		if len(filename.split(os.path.sep)) > 3:
			# run the update (this might be called from another thread)
			splits = filename.split(os.path.sep)
			if splits[1] == "config":
				if len(splits) > 3:
					asyncio.run_coroutine_threadsafe(
						self.update_configs(filename), self._asyncio_loop)

	def on_created(self, event: FileSystemEvent):
		filename = event.key[1]  # type: str
		splits = filename.split(os.path.sep)
		if get_directory_from_file(filename) == SOCKET_PATH:
			asyncio.run_coroutine_threadsafe(self.on_add_sockets(), self._asyncio_loop)

	def on_deleted(self, event):
		filename = event.key[1]  # type: str
		filename.split(os.path.sep)
		if get_directory_from_file(filename) == SOCKET_PATH:
			asyncio.run_coroutine_threadsafe(
				self.on_delete_sockets(), self._asyncio_loop)

	async def on_add_sockets(self):
		async with self.socket_lock:
			new_monitor_sockets = {}  # type: Dict[str, str]
			new_scraper_sockets = {}  # type: Dict[str, str]
			for filename in os.listdir(SOCKET_PATH):
				splits = filename.split(".")
				if splits[0] == "Monitor" and splits[1] not in self.monitor_sockets:
					new_monitor_sockets[splits[1]] = os.path.sep.join([SOCKET_PATH, filename])
				elif splits[0] == "Scraper" and splits[1] not in self.scraper_sockets:
					new_scraper_sockets[splits[1]] = os.path.sep.join([SOCKET_PATH, filename])

			alive_monitor_sockets, alive_scraper_sockets = await asyncio.gather(self.get_alive_sockets(new_monitor_sockets.values()), self.get_alive_sockets(new_scraper_sockets.values()))

			for class_name in new_monitor_sockets:
				if new_monitor_sockets[class_name] in alive_monitor_sockets:
					self.monitor_sockets[class_name] = new_monitor_sockets[class_name]

			for class_name in new_scraper_sockets:
				if new_scraper_sockets[class_name] in alive_scraper_sockets:
					self.scraper_sockets[class_name] = new_scraper_sockets[class_name]

	async def on_delete_sockets(self):
		async with self.socket_lock:
			monitor_sockets = []
			scraper_sockets = []
			for f in list(os.listdir(SOCKET_PATH)):
				if f.startswith("Monitor."):
					monitor_sockets.append(f)
				elif f.startswith("Scraper."):
					scraper_sockets.append(f)

			new_monitor_sockets = copy.deepcopy(self.monitor_sockets)
			new_scraper_sockets = copy.deepcopy(self.scraper_sockets)

			for class_name in self.monitor_sockets:
				if "Monitor." + class_name not in monitor_sockets:
					new_monitor_sockets.pop(class_name)
			for class_name in self.scraper_sockets:
				if "Scraper." + class_name not in scraper_sockets:
					new_scraper_sockets.pop(class_name)

			self.monitor_sockets = new_monitor_sockets
			self.scraper_sockets = new_scraper_sockets

	async def get_alive_sockets(self, sockets: List[str]) -> List[str]:
		tasks = []
		for socket in sockets:
			cmd = Cmd()
			cmd.cmd = COMMANDS.PING
			tasks.append(self.make_request(socket, cmd))

		responses = await asyncio.gather(*tasks)  # type: List[Response]
		alive = []
		for response, socket in zip(responses, sockets):
			if response.success:
				alive.append(socket)

		return alive

	async def update_configs(self, filename: str):
		'''Reads the config file and updates the interested monitors/scrapers'''
		self.general_logger.debug(f"File {filename} has changed!")
		if filename.endswith(".json"):
			try:
				with open(filename, "r") as f:
					j = json.load(f)
			except JSONDecodeError:
				self.general_logger.warning(
					f"File {filename} was changed but constains invalid json data")
				return

			splits = filename.split(os.path.sep)
			commands = []  # List[Cmd]
			cmd = None  # Enum
			sock_paths = []   # type: List[str]
			# if it's from the monitors folder:
			if splits[2] == "monitors":
				# we are interested in configs, whitelist, blacklist, webhooks
				if splits[3] == "whitelists.json":
					cmd = COMMANDS.SET_WHITELIST
				elif splits[3] == "configs.json":
					cmd = COMMANDS.SET_CONFIG
				elif splits[3] == "blacklists.json":
					cmd = COMMANDS.SET_BLACKLIST
				elif splits[3] == "webhooks.json":
					cmd = COMMANDS.SET_WEBHOOKS
				else:
					cmd = None
				if cmd:
					# for every monitor socket
					for sockname in os.listdir(SOCKET_PATH):
						if sockname.startswith("Monitor."):
							# add command and socket path to the list of todo
							name = sockname.split(".")[1]
							if (name in j):
								c = Cmd()
								c.cmd = cmd
								# send only the corresponding part to the monitor
								c.payload = j[name]
								commands.append(c)
								sock_paths.append(os.path.sep.join([SOCKET_PATH, sockname]))

			elif splits[2] == "scrapers":
				# we are interested in configs, whitelist, blacklist
				if splits[3] == "whitelists.json":
					cmd = COMMANDS.SET_WHITELIST
				elif splits[3] == "configs.json":
					cmd = COMMANDS.SET_CONFIGS
				elif splits[3] == "blacklists.json":
					cmd = COMMANDS.SET_BLACKLIST
				else:
					cmd = None
				if cmd:
					# for every scraper socket
					for sockname in os.listdir(SOCKET_PATH):
						if sockname.startswith("Scraper."):
							# add command and socket path to the list of todo
							name = sockname.split(".")[1]
							if (name in j):
								c = Cmd()
								c.cmd = cmd
								# send only the corresponding part to the scraper
								c.payload = j[name]
								commands.append(c)
								sock_paths.append(os.path.sep.join([SOCKET_PATH, sockname]))
			else:
				self.general_logger.debug("File not useful.")
				return

			# prepare to make all the async requests
			tasks = []
			for sock_path, command in zip(sock_paths, commands):
				tasks.append(self.make_request(sock_path, command))

			# send the requests
			responses = await asyncio.gather(*tasks)   # List[Response]

			for response in responses:
				if response.error.value:
					self.general_logger.warning(f"Failed to update config: {response.error}")

	async def on_server_stop(self):
		async with self._loop_lock:
			# stop the config watcher
			self.config_watcher.stop()
			self.config_watcher.join()

			if self.shutdown_all_on_exit:
				# get all the existing sockets
				sockets = []  # type: List[str]
				tasks = []
				for sockname in os.listdir(SOCKET_PATH):
					if sockname.startswith("Scraper.") or sockname.startswith("Monitor."):
						cmd = Cmd()
						cmd.cmd = COMMANDS.STOP
						sockets.append(sockname)

						tasks.append(self.make_request(
							f"{SOCKET_PATH}{os.path.sep}{sockname}", cmd))

				# send request to stop
				responses = await asyncio.gather(*tasks)   # type: List[Response]

				for sockname, r in zip(sockets, responses):
					# if an error happened...
					if r.error.value:
						# if the socket was not used remove it
						if r.error == ERRORS.SOCKET_COULDNT_CONNECT:
							os.remove(os.path.sep.join([SOCKET_PATH, sockname]))
							self.general_logger.info(
								f"{SOCKET_PATH}{os.path.sep}{sockname} was removed because unavailable")
						# else something else happened, dont do anything
						else:
							self.general_logger.warning(
								f"Error occurred while attempting to stop {sockname}: {r.error}")
					# ok
					else:
						self.general_logger.warning(f"{sockname} was successfully stopped")

		self._asyncio_loop.stop()
		self.general_logger.info("Shutting down...")
		return okResponse()

	async def check_status(self):
		'''Main MonitorManager loop. Every second it checks its monitored processes and looks if they are still alive, possibly reporting any exit code'''
		while True:
			async with self._loop_lock:
				new_monitor_processes = {}
				for class_name in self.monitor_processes:
					monitor = self.monitor_processes[class_name]["process"]
					if monitor.poll() is not None:
						log = f"Monitor {class_name} has stopped with code: {monitor.returncode}"
						if monitor.returncode:
							self.general_logger.warning(log)
							if WEBHOOK_CONFIG.CRASH_WEBHOOK:
								data = {"content": log}
								await self.client.fetch(WEBHOOK_CONFIG.CRASH_WEBHOOK, method="POST", body=json.dumps(data), headers={"content-type": "application/json"}, raise_error=False)
						else:
							self.general_logger.info(log)
					else:
						new_monitor_processes[class_name] = self.monitor_processes[class_name]
				self.monitor_processes = new_monitor_processes

				new_scraper_processes = {}
				for class_name in self.scraper_processes:
					scraper = self.scraper_processes[class_name]["process"]
					if scraper.poll() is not None:
						log = f"Scraper {class_name} has stopped with code: {scraper.returncode}"
						if scraper.returncode:
							self.general_logger.warning(log)
							if WEBHOOK_CONFIG.CRASH_WEBHOOK:
								data = {"content": log}
								await self.client.fetch(WEBHOOK_CONFIG.CRASH_WEBHOOK, method="POST", body=json.dumps(data), headers={"content-type": "application/json"}, raise_error=False)
						else:
							self.general_logger.info(log)
					else:
						new_scraper_processes[class_name] = self.scraper_processes[class_name]
				self.scraper_processes = new_scraper_processes
			await asyncio.sleep(1)

	async def on_add_monitor(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_monitor_args)
		if success:
			payload = cast(Dict[str, Any], cmd.payload)
			success, reason = await self.add_monitor(
				payload["filename"], payload["class_name"], payload.get("delay", None))
			if success:
				r = okResponse()
			else:
				r.error = ERRORS.MM_COULDNT_ADD_MONITOR
				r.info = reason
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_add_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_scraper_args)
		if success:
			payload = cast(Dict[str, Any], cmd.payload)
			success = await self.add_scraper(
				payload["filename"], payload["class_name"], payload.get("delay", None))
			if success:
				r = okResponse()
			else:
				r.error = ERRORS.MM_COULDNT_ADD_SCRAPER
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_add_monitor_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_monitor_scraper_args)
		if success:
			payload = cast(Dict[str, Any], cmd.payload)
			success = await self.add_monitor_scraper(
				payload["filename"], payload["class_name"], payload.get("monitor_delay", None), payload.get("scraper_delay", None))
			if success:
				r = okResponse()
			else:
				r.error = ERRORS.MM_COULDNT_ADD_MONITOR_SCRAPER
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_stop_monitor(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			payload = cast(Dict[str, Any], cmd.payload)
			command = Cmd()
			command.cmd = COMMANDS.STOP
			r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", command)
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_stop_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			payload = cast(Dict[str, Any], cmd.payload)
			command = Cmd()
			command.cmd = COMMANDS.STOP
			r = await self.make_request(f"{SOCKET_PATH}/Scraper.{payload['class_name']}", command)
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_stop_monitor_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			r1, r2 = await asyncio.gather(self.on_stop_monitor(cmd), self.on_stop_scraper(cmd))
			if not r1.error.value and not r2.error.value:
				r = okResponse()
			else:
				r.error = ERRORS.MM_COULDNT_STOP_MONITOR_SCRAPER
				r.info = ""
				for i in [r1.info, r2.info]:
					if i:
						r.info += i + "; "
		else:
			r.error = ERRORS.MISSING_PAYLOAD_ARGS
			r.info = f"Missing arguments: {missing}"
		return r

	async def on_get_monitor_status(self, cmd: Cmd) -> Response:
		process_status = {}
		for class_name in self.monitor_processes:
			start = self.monitor_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			process_status[class_name] = {"Started at": start}
		sockets_status = {}
		for class_name in self.monitor_sockets:
			sockets_status[class_name] = {class_name: self.monitor_sockets[class_name]}
		response = okResponse()
		response.payload = {
			"monitored_processes": process_status, "available_sockets": sockets_status}
		return response

	async def on_get_scraper_status(self, cmd: Cmd) -> Response:
		process_status = {}
		for class_name in self.scraper_processes:
			start = self.scraper_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			process_status[class_name] = {"Started at": start}
		sockets_status = {}
		for class_name in self.scraper_sockets:
			sockets_status[class_name] = {class_name: self.scraper_sockets[class_name]}
		response = okResponse()
		response.payload = {
			"monitored_processes": process_status, "available_sockets": sockets_status}
		return response

	async def on_get_status(self, cmd: Cmd) -> Response:
		ms = await self.on_get_monitor_status(cmd)
		ss = await self.on_get_scraper_status(cmd)
		response = okResponse()
		msp = cast(Dict[str, Any], ms.payload)  # type: Dict[str, Any]
		ssp = cast(Dict[str, Any], ss.payload)  # type: Dict[str, Any]
		response.payload = {
			"monitors": msp, "scrapers": ssp}
		return response

	async def add_monitor(self, filename: str, class_name: str, delay: Optional[Union[int, float]]):
		if class_name in self.monitor_processes:
			self.general_logger.debug(
				f"Tried to add an already existing monitor ({filename}.{class_name})")
			return False, "Monitor already started."

		cmd = f"nohup python -m monitors.{filename} --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.general_logger.debug(f"Starting {filename}.{class_name}...")
		monitor = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

		await asyncio.sleep(2)  # wait to check if process is still alive

		if monitor.poll() is not None:
			success = False
			msg = f"Failed to start monitor {filename}.{class_name}"
			self.general_logger.warning(
				f"Tried to start {filename}.{class_name} but failed")
		else:
			self.general_logger.info(
				f"Added monitor {class_name} with pid {monitor.pid}")
			self.monitor_processes[class_name] = {
				"process": monitor,
				"start": datetime.now()
			}
			success = True
			msg = ""
		return success, msg

	async def add_scraper(self, filename: str, class_name: str, delay: Optional[Union[int, float]]):
		if class_name in self.scraper_processes:
			self.general_logger.debug(
				f"Tried to add an already existing scraper ({filename}.{class_name})")
			return False, "Scraper already started."

		cmd = f"nohup python -m scrapers.{filename} --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.general_logger.debug(f"Starting {filename}.{class_name}...")
		scraper = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

		await asyncio.sleep(2)  # wait to check if process is still alive

		if scraper.poll() is not None:
			success = False
			msg = f"Failed to start scraper {filename}.{class_name}"
			self.general_logger.warning(
				f"Tried to start {filename}.{class_name} but failed")
		else:
			self.general_logger.info(
				f"Added scraper {class_name} with pid {scraper.pid}")
			self.scraper_processes[class_name] = {
				"process": scraper,
				"start": datetime.now()
			}
			success = True
			msg = ""
		return success, msg

	async def add_monitor_scraper(self, filename: str, class_name: str, scraper_delay: Optional[Union[int, float]], monitor_delay: Optional[Union[int, float]]):
		(s1, msg1), (s2, msg2) = await asyncio.gather(self.add_monitor(filename, class_name, monitor_delay), self.add_scraper(filename, class_name, scraper_delay))
		s = s1 and s2
		msg = "" + (msg1 if not s1 else "") + (msg2 if not s2 else "")
		return s, msg

	async def on_get_config(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.GET_CONFIG}))
		return r

	async def on_set_config(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.SET_CONFIG, "payload": payload}))
		return r

	async def on_get_whitelist(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.GET_WHITELIST}))
		return r

	async def on_set_whitelist(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.SET_WHITELIST, "payload": payload}))
		return r

	async def on_get_blacklist(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.GET_BLACKLIST}))
		return r

	async def on_set_blacklist(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.SET_CONFIG, "payload": payload}))
		return r

	async def on_get_webhooks(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.GET_WEBHOOKS}))
		return r

	async def on_set_webhooks(self, cmd: Cmd) -> Response:
		payload = cast(Dict[str, Any], cmd.payload)
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": COMMANDS.SET_WEBHOOKS, "payload": payload}))
		return r


if __name__ == "__main__":
	MonitorManager().start()
