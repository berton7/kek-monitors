import asyncio
import os
from pprint import pprint

from configs.config import COMMANDS, SOCKET_PATH
from utils.server.msg import *


async def make_request(socket_path, cmd, expect_response=True):
	if os.path.exists(socket_path):
		try:
			reader, writer = await asyncio.open_unix_connection(socket_path)
			writer.write(cmd.get_bytes())
			writer.write_eof()

			if expect_response:
				response = Response(await reader.read())

				writer.close()
				return response
			return okResponse()
		except ConnectionRefusedError:
			pass
	r = badResponse()
	r.info = f"Socket {socket_path} unavailable"
	return r

if __name__ == "__main__":
	cmd = Cmd()
	cmd.cmd = COMMANDS.MM_STOP_MONITOR_MANAGER
	pprint(asyncio.run(make_request(
		f"{SOCKET_PATH}/MonitorManager", cmd)).get_json())
