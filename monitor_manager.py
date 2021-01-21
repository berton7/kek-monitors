import asyncio
import os
import pickle
import shlex
import subprocess
import time
from datetime import datetime
from typing import List, Optional, Tuple, Union, Dict, Any

import utils.tools
from configs.config import *
from utils.server.server import Server
from utils.server.msg import *


class MonitorManager(Server):
	'''This can be used to manage monitors/scrapers with an external api.'''

	def __init__(self):
		logger_name = "Executable.MonitorManager"
		super().__init__(logger_name, f"{SOCKET_PATH}/MonitorManager")
		self.general_logger = utils.tools.get_logger(logger_name + ".General")
		self.cmd_to_callback[ADD_MONITOR] = self.on_add_monitor
		self.cmd_to_callback[ADD_SCRAPER] = self.on_add_scraper
		self.cmd_to_callback[ADD_MONITOR_SCRAPER] = self.on_add_monitor_scraper
		self.cmd_to_callback[STOP_MONITOR] = self.on_stop_monitor
		self.cmd_to_callback[STOP_SCRAPER] = self.on_stop_scraper
		self.cmd_to_callback[STOP_MONITOR_SCRAPER] = self.on_stop_monitor_scraper
		self.cmd_to_callback[GET_MONITOR_STATUS] = self.on_get_monitor_status
		self.cmd_to_callback[GET_SCRAPER_STATUS] = self.on_get_scraper_status
		self.cmd_to_callback[GET_MONITOR_SCRAPER_STATUS] = self.on_get_status

		# self.asyncio_loop.create_task(self.init_server())

		self.monitor_processes = {}  # type: Dict[str, Dict[str, Any]]
		self.scraper_processes = {}  # type: Dict[str, Dict[str, Any]]
		self.add_scraper_args = self.add_monitor_args = self.add_monitor_scraper_args = [
			"filename", "class_name"]
		self.stop_args = ["class_name"]
		self.has_to_quit = False

	def start(self):
		self.asyncio_loop.run_until_complete(self.check_status())

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

		self.general_logger("Shutting down...")

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
			r = await self.make_request(f"{SOCKET_PATH}/Monitor.{payload['class_name']}", Cmd({"cmd": STOP}))
		else:
			r.reason = f"Missing arguments: {missing}"
		return r

	async def on_stop_scraper(self, cmd: Cmd) -> Response:
		r = badResponse()
		success, missing = cmd.has_valid_args(self.stop_args)
		if success:
			payload = cmd.payload
			r = await self.make_request(f"{SOCKET_PATH}/Scraper.{payload['class_name']}", Cmd({"cmd": STOP}))
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
		msg = "" + (msg1 if s1 else "") + (msg2 if s2 else "")
		return s, msg


if __name__ == "__main__":
	MonitorManager().start()
