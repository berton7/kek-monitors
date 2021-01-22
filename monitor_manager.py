import asyncio
from json.decoder import JSONDecodeError
import os
import shlex
import subprocess
from datetime import datetime
from typing import Optional, Union, Dict, Any

import utils.tools
from configs.config import COMMANDS, SOCKET_PATH
from utils.server.server import Server
from utils.server.msg import *
from watchdog import observers
from watchdog.events import FileSystemEvent, FileSystemEventHandler
import json


class MonitorManager(Server, FileSystemEventHandler):
	'''This can be used to manage monitors/scrapers with an external api.'''

	def __init__(self):
		logger_name = "Executable.MonitorManager"
		super().__init__(logger_name, f"{SOCKET_PATH}/MonitorManager")
		super(Server).__init__()
		self.general_logger = utils.tools.get_logger(logger_name + ".General")
		self.cmd_to_callback[COMMANDS.MM_STOP_MONITOR_MANAGER] = self.stop_serving
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
		self.add_scraper_args = self.add_monitor_args = self.add_monitor_scraper_args = [
			"filename", "class_name"]
		self.stop_args = ["class_name"]

		self.config_watcher = observers.Observer()
		self.config_watcher.schedule(self, "./configs", True)
		self.has_to_quit = False

	def start(self):
		self.config_watcher.start()
		self.asyncio_loop.run_until_complete(self.check_status())

	def on_modified(self, event: FileSystemEvent):
		filename = event.key[1]  # type: str
		if len(filename.split(os.path.sep)) > 3:
			asyncio.run_coroutine_threadsafe(
				self.update_configs(filename), self.asyncio_loop)

	async def update_configs(self, filename: str):
		self.general_logger.debug(f"File {filename} has changed!")
		if filename.endswith(".json"):
			try:
				with open(filename, "r") as f:
					j = json.load(f)
			except JSONDecodeError:
				self.general_logger.warning(
					
					f"File {filename} was changed but constains invalid json data: {j}")
				return
			splits = filename.split(os.path.sep)
			commands = []  # List[Cmd]
			cmd = None  # Enum
			sock_paths = []   # type: List[str]
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
					for sockname in os.listdir(SOCKET_PATH):
						if sockname.startswith("Monitor."):
							name = sockname.split(".")[1]
							if (name in j):
								c = Cmd()
								c.cmd = cmd
								c.payload = j[name]
								commands.append(c)
								sock_paths.append(os.path.sep.join([SOCKET_PATH,  sockname]))

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
					for sockname in os.listdir(SOCKET_PATH):
						if sockname.startswith("Scraper."):
							name = sockname.split(".")[1]
							if (name in j):
								c = Cmd()
								c.cmd = cmd
								c.payload = j[name]
								commands.append(c)
								sock_paths.append(os.path.sep.join([SOCKET_PATH,  sockname]))
			else:
				self.general_logger.debug("File not useful.")
				return

			tasks = []
			for sock_path, command in zip(sock_paths, commands):
				tasks.append(self.make_request(sock_path, command))

			responses = await asyncio.gather(*tasks)   # List[Response]

			for response in responses:
				if not response.success:
					self.general_logger.warning(f"Failed to update config: {response.reason}")

	async def on_server_stop(self):
		self.config_watcher.stop()
		self.config_watcher.join()
		for sockname in os.listdir(SOCKET_PATH):
			if sockname.startswith("Scraper.") or sockname.startswith("Scraper."):
				cmd = Cmd()
				cmd.cmd = COMMANDS.STOP
				r = await self.make_request(sockname, cmd)
				if not r.success and r.reason == f"Socket {sockname} unavailable":
					os.remove(os.path.sep.join([SOCKET_PATH, sockname]))

		self.has_to_quit = True

	async def check_status(self):
		while not self.has_to_quit:
			new_monitor_processes = {}
			for class_name in self.monitor_processes:
				monitor = self.monitor_processes[class_name]["process"]
				if monitor.poll() is not None:
					self.general_logger.info(
						f"Monitor {class_name} has stopped with code: {monitor.returncode}")
				else:
					new_monitor_processes[class_name] = self.monitor_processes[class_name]
			self.monitor_processes = new_monitor_processes

			new_scraper_processes = {}
			for class_name in self.scraper_processes:
				scraper = self.scraper_processes[class_name]["process"]
				if scraper.poll() is not None:
					self.general_logger.info(
						f"Scraper {class_name} has stopped with code: {scraper.returncode}")
				else:
					new_scraper_processes[class_name] = self.scraper_processes[class_name]
			self.scraper_processes = new_scraper_processes
			await asyncio.sleep(1)

		self.general_logger.info("Shutting down...")

	async def on_add_monitor(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_monitor_args)
		if success:
			payload = cmd.payload
			success, reason = await self.add_monitor(
				payload["filename"], payload["class_name"], payload.get("delay", None))
			if success:
				r = okResponse()
			else:
				r.reason = reason
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_add_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_scraper_args)
		if success:
			payload = cmd.payload
			success, reason = await self.add_scraper(
				payload["filename"], payload["class_name"], payload.get("delay", None))
			if success:
				r = okResponse()
			else:
				r.reason = reason
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_add_monitor_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.add_monitor_scraper_args)
		if success:
			payload = cmd.payload
			success, reason = await self.add_monitor_scraper(
				payload["filename"], payload["class_name"], payload.get("monitor_delay", None), payload.get("scraper_delay", None))
			if success:
				r = okResponse()
			else:
				r.reason = reason
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_stop_monitor(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			payload = cmd.payload
			command = Cmd()
			command.cmd = COMMANDS.STOP
			r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", command)
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_stop_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			payload = cmd.payload
			command = Cmd()
			command.cmd = COMMANDS.STOP
			r = await self.make_request(f"{SOCKET_PATH}/Scraper.{payload['class_name']}", command)
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_stop_monitor_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			r1, r2 = await asyncio.gather(self.on_stop_monitor(cmd), self.on_stop_scraper(cmd))
			if r1.success and r2.success:
				r = okResponse()
			else:
				r.reason = "" + (r1.reason + "; " if r1.reason else "") + \
                                    (r2.reason if r2.reason else "")
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_get_monitor_status(self, cmd: Cmd) -> Response:
		status = {}
		for class_name in self.monitor_processes:
			start = self.monitor_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			status[class_name] = {"Started at": start}
		response = okResponse()
		response.payload = {"status": status}
		return response

	async def on_get_scraper_status(self, cmd: Cmd) -> Response:
		status = {}
		for class_name in self.scraper_processes:
			start = self.scraper_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			status[class_name] = {"Started at": start}
		response = okResponse()
		response.payload = {"status": status}
		return response

	async def on_get_status(self, cmd: Cmd) -> Response:
		ms = await self.on_get_monitor_status(cmd)
		ss = await self.on_get_scraper_status(cmd)
		response = okResponse()
		response.payload = {"status": {"monitors": ms.payload[
                    "status"], "scrapers": ss.payload["status"]}}
		return response

	async def add_monitor(self, filename: str, class_name: str, delay: Optional[Union[int, float]]):
		if class_name in self.monitor_processes:
			self.general_logger.debug(
				f"Tried to add an already existing monitor ({filename}.{class_name})")
			return False, "Monitor already started."

		cmd = f"python monitors{os.path.sep}{filename}.py --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.general_logger.debug(f"Starting {filename}.{class_name}...")
		monitor = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

		cmd = f"python scrapers{os.path.sep}{filename}.py --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.general_logger.debug(f"Starting {filename}.{class_name}...")
		scraper = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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

	async def on_get_config(self, cmd:Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.GET_CONFIG}))
		return r

	async def on_set_config(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.SET_CONFIG, "payload": cmd.payload}))
		return r

	async def on_get_whitelist(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.GET_WHITELIST}))
		return r

	async def on_set_whitelist(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.SET_WHITELIST, "payload": cmd.payload}))
		return r

	async def on_get_blacklist(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.GET_BLACKLIST}))
		return r

	async def on_set_blacklist(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.SET_CONFIG, "payload": cmd.payload}))
		return r

	async def on_get_webhooks(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.GET_WEBHOOKS}))
		return r

	async def on_set_webhooks(self, cmd: Cmd) -> Response:
		r = await self.make_request(f"{SOCKET_PATH}/Monitor.{cmd.payload['class_name']}", Cmd({"cmd": COMMANDS.SET_WEBHOOKS, "payload": cmd.payload}))
		return r

if __name__ == "__main__":
	MonitorManager().start()
