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


class Arguments(object):
	'''Helper class to check validity of messages.'''

	def __init__(self, *args: List[str]):
		'''Initialize with a list of args that must appear in the payload of a message.'''
		self.args = args

	def check_msg(self, message) -> Tuple[bool, str]:
		'''Check if message has a payload and if all args are present in it.'''
		if "payload" not in message:
			return False, "payload not provided"
		for arg in self.args:
			if arg not in message["payload"]:
				return False, f"{arg} not provided"
		return True, ""


class MonitorManager(object):
	'''This can be used to manage monitors/scrapers with an external api.'''

	def __init__(self):
		self.monitor_processes = {}  # type: Dict[str, Dict[str, Any]]
		self.scraper_processes = {}  # type: Dict[str, Dict[str, Any]]

		self.add_scraper_args = self.add_monitor_args = self.add_monitor_scraper_args = Arguments(
			"filename", "class_name")

		self.stop_args = Arguments("class_name")

		self.loop = asyncio.get_event_loop()
		self.loop.create_task(self.init_server())
		self.loop.create_task(self.check_status())

		self.logger = utils.tools.get_logger("Executable.MonitorManager")

	def start(self):
		self.loop.run_forever()

	async def init_server(self):
		self.server = await asyncio.start_unix_server(self.handle_msg, f"{SOCKET_PATH}/MonitorManager")

		addr = self.server.sockets[0].getsockname()
		self.logger.debug(f'Serving on {addr}')

		async with self.server:
			await self.server.serve_forever()

	async def check_status(self):
		while True:
			new_monitor_processes = {}
			for class_name in self.monitor_processes:
				monitor = self.monitor_processes[class_name]["process"]
				if monitor.poll() is not None:
					self.logger.info(
						f"Monitor {class_name} has stopped with code: {monitor.returncode}")
				else:
					new_monitor_processes[class_name] = self.monitor_processes[class_name]
			self.monitor_processes = new_monitor_processes

			new_scraper_processes = {}
			for class_name in self.scraper_processes:
				scraper = self.scraper_processes[class_name]["process"]
				if scraper.poll() is not None:
					self.logger.info(
						f"Scraper {class_name} has stopped: {scraper.returncode}")
				else:
					new_scraper_processes[class_name] = self.scraper_processes[class_name]
			self.scraper_processes = new_scraper_processes
			await asyncio.sleep(1)

	async def handle_msg(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		data = await reader.read()
		addr = writer.get_extra_info('peername')
		self.logger.debug(f"Received from {addr!r}")

		message = pickle.loads(data)
		# set
		if message["cmd"] == ADD_MONITOR:
			success, msg = self.add_monitor_args.check_msg(message)
			if success:
				success, msg = self.add_monitor(
					message["payload"]["filename"], message["payload"]["class_name"], message["payload"].get("delay", None))
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})
		elif message["cmd"] == ADD_SCRAPER:
			success, msg = self.add_scraper_args.check_msg(message)
			if success:
				success, msg = self.add_scraper(
					message["payload"]["filename"], message["payload"]["class_name"], message["payload"].get("delay", None))
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})
		elif message["cmd"] == ADD_MONITOR_SCRAPER:
			success, msg = self.add_monitor_scraper_args.check_msg(message)
			if success:
				success, msg = self.add_monitor_scraper(message["payload"]["filename"], message["payload"]
				                                        ["class_name"], message["payload"].get("monitor_delay", None), message["payload"].get("scraper_delay", None))
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})

		# stop
		elif message["cmd"] == STOP_MONITOR:
			success, msg = self.stop_args.check_msg(message)
			if success:
				success, msg = await self.stop_monitor(message["payload"]["class_name"])
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})

		elif message["cmd"] == STOP_SCRAPER:
			success, msg = self.stop_args.check_msg(message)
			if success:
				success, msg = await self.stop_scraper(message["payload"]["class_name"])
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})

		elif message["cmd"] == STOP_MONITOR_SCRAPER:
			success, msg = self.stop_args.check_msg(message)
			if success:
				success, msg = await self.stop_monitor_scraper(message["payload"]["class_name"])
				if success:
					response = pickle.dumps({"success": True})
				else:
					response = pickle.dumps({"success": False, "msg": msg})
			else:
				response = pickle.dumps({"success": False, "msg": msg})
		# get
		elif message["cmd"] == GET_MONITOR_STATUS:
			response = pickle.dumps(self.get_monitor_status())
		elif message["cmd"] == GET_SCRAPER_STATUS:
			response = pickle.dumps(self.get_scraper_status())
		elif message["cmd"] == GET_MONITOR_SCRAPER_STATUS:
			response = pickle.dumps(self.get_monitor_scraper_status())
		else:
			response = pickle.dumps({"success": False, "msg": "cmd not recognized"})

		writer.write(response)
		writer.write_eof()
		await writer.drain()

		self.logger.debug("Close the connection")
		writer.close()

	def add_monitor(self, filename: str, class_name: str, delay: Optional[Union[int, float]]):
		if class_name in self.monitor_processes:
			self.logger.debug(
				f"Tried to add an already existing monitor ({filename}.{class_name})")
			return False, "Monitor already started."

		cmd = f"python monitors{os.path.sep}{filename}.py --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.logger.debug(f"Starting {filename}.{class_name}...")
		monitor = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

		time.sleep(2)  # wait to check if process is still alive

		if monitor.poll() is not None:
			success = False
			msg = f"Failed to start monitor {filename}.{class_name}"
			self.logger.warning(f"Tried to start {filename}.{class_name} but failed")
		else:
			self.logger.info(f"Added monitor {class_name} with pid {monitor.pid}")
			self.monitor_processes[class_name] = {
				"process": monitor,
				"start": datetime.now()
			}
			success = True
			msg = ""
		return success, msg

	def add_scraper(self, filename: str, class_name: str, delay: Optional[Union[int, float]]):
		if class_name in self.scraper_processes:
			self.logger.debug(
				f"Tried to add an already existing scraper ({filename}.{class_name})")
			return False, "Scraper already started."

		cmd = f"python scrapers{os.path.sep}{filename}.py --no-output"
		if delay:
			cmd += f" --delay {str(delay)}"

		self.logger.debug(f"Starting {filename}.{class_name}...")
		scraper = subprocess.Popen(shlex.split(
			cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

		time.sleep(2)  # wait to check if process is still alive

		if scraper.poll() is not None:
			success = False
			msg = f"Failed to start scraper {filename}.{class_name}"
			self.logger.warning(f"Tried to start {filename}.{class_name} but failed")
		else:
			self.logger.info(f"Added scraper {class_name} with pid {scraper.pid}")
			self.scraper_processes[class_name] = {
				"process": scraper,
				"start": datetime.now()
			}
			success = True
			msg = ""
		return success, msg

	def add_monitor_scraper(self, filename: str, class_name: str, scraper_delay: Optional[Union[int, float]], monitor_delay: Optional[Union[int, float]]):
		success, msg = self.add_monitor(filename, class_name, monitor_delay)
		if success:
			success, msg = self.add_scraper(filename, class_name, scraper_delay)
		return success, msg

	async def stop_monitor(self, class_name: str) -> Tuple[bool, str]:
		success = False
		msg = ""
		monitor_sock = f"{SOCKET_PATH}/Monitor.{class_name}"
		try:
			reader, writer = await asyncio.open_unix_connection(monitor_sock)

			writer.write(pickle.dumps({"cmd": STOP}))
			writer.write_eof()

			data = await reader.read()

			writer.close()
			success = True
			msg = ""
		except (ConnectionRefusedError, FileNotFoundError):
			self.logger.exception(f"Couldn't connect to socket {monitor_sock}")
			success = False
			msg = f"Couldn't connect to socket {monitor_sock}"

		return success, msg

	async def stop_scraper(self, class_name: str) -> Tuple[bool, str]:
		success = False
		msg = ""
		scraper_sock = f"{SOCKET_PATH}/Scraper.{class_name}"
		try:
			reader, writer = await asyncio.open_unix_connection(scraper_sock)

			writer.write(pickle.dumps({"cmd": STOP}))
			writer.write_eof()

			data = await reader.read()

			writer.close()
			success = True
			msg = ""
		except (ConnectionRefusedError, FileNotFoundError):
			self.logger.exception(f"Couldn't connect to socket {scraper_sock}")
			success = False
			msg = f"Couldn't connect to socket {scraper_sock}"

		return success, msg

	async def stop_monitor_scraper(self, class_name: str) -> Tuple[bool, str]:
		success, msg = await self.stop_monitor(class_name)
		newsuccess, newmsg = await self.stop_scraper(class_name)
		rsuccess = success and newsuccess
		rmsg = " ".join([msg, newmsg])
		return rsuccess, rmsg

	def get_monitor_status(self):
		response = {}
		for class_name in self.monitor_processes:
			start = self.monitor_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			response[class_name] = {"Started at": start}
		return response

	def get_scraper_status(self):
		response = {}
		for class_name in self.scraper_processes:
			start = self.scraper_processes[class_name]["start"].strftime(
				"%m/%d/%Y, %H:%M:%S")
			response[class_name] = {"Started at": start}
		return response

	def get_monitor_scraper_status(self):
		mr = self.get_monitor_status()
		ms = self.get_scraper_status()
		return {"monitors": mr, "scrapers": ms}


if __name__ == "__main__":
	MonitorManager().start()
