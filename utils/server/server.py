if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from pickle import TRUE
from utils.tools import get_logger
from utils.server.msg import *
from configs.config import *
import os


class Server(object):
	def __init__(self, logger_name: str, server_path: str):
		self.server_logger = get_logger(logger_name + ".Server")
		self.server_path = server_path
		# init asyncio stuff
		self.asyncio_loop = asyncio.get_event_loop()
		self.server_task = self.asyncio_loop.create_task(self.init_server())

		self.cmd_to_callback = {
			STOP: self.stop_serving
		}

	async def init_server(self):
		'''Initialise the underlying socket server, to allow communication between monitor/scraper.'''
		self.server = await asyncio.start_unix_server(self.handle_msg, self.server_path)

		addr = self.server.sockets[0].getsockname()
		self.server_logger.debug(f'Serving on {addr}')

		await self.server.start_serving()

	async def stop_serving(self, msg: Cmd):
		self.server_logger.info("Closing server...")
		self.server.close()
		await self.server.wait_closed()
		os.remove(self.server_path)
		self.server_logger.info("Server successfully closed.")
		await self.on_server_stop()
		return okResponse()

	async def on_server_stop(self):
		pass

	async def handle_msg(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		'''Handle incoming messages.'''
		msg = Cmd(await reader.read())
		addr = writer.get_extra_info('peername')
		print_addr = addr if addr else "localhost"
		self.server_logger.debug(f"Received from {print_addr}")

		msg_cmd = msg.get_cmd()
		for cmd in self.cmd_to_callback:
			if cmd == msg_cmd:
				response = await self.cmd_to_callback[cmd](msg)
				break
		else:
			response = badResponse()
			response.set_reason("Unrecognized cmd.")

		writer.write(response.to_bytes())
		writer.write_eof()
		await writer.drain()

		self.server_logger.debug(f"Closed connection from {print_addr}")
		writer.close()
