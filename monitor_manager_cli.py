import asyncio
from configs.config import COMMANDS, SOCKET_PATH
import os
from utils.server.msg import *
import sys
from pprint import pprint


async def make_request(socket_path, cmd, expect_response):
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
			#self.server_logger.exception(f"Couldn't connect to socket {socket_path}")
			pass
	r = badResponse()
	r.reason = f"Socket {socket_path} unavailable"
	return r

if __name__ == "__main__":
	args = sys.argv
	if len(args) < 2:
		print("Usage: python monitor_manager_cli.py <cmd> [payload]")
		exit(1)
	cmd = COMMANDS.__dict__.get(args[1], None)
	if not cmd:
		print("Inserted cmd does not exist!")
		exit(2)
	string_cmd = args[1]
	payload = {}
	if len(args) > 2:
		if not len(args) % 2:
			for index, term in enumerate(args[2:]):
				if not index % 2:
					if not term.startswith("--"):
						print("You must start every payload key with \"--\"")
						exit(4)
					payload[term[2:]] = args[3 + index]
		else:
			print("Incorrect number of payload options!")
			exit(3)
	command = Cmd()
	command.cmd = cmd
	command.payload = payload
	print(f"Command: {command.cmd}")
	print(f"Payload: {command.payload}")
	print("Executing request...")
	response = asyncio.run(make_request(
		f"{SOCKET_PATH}/MonitorManager", command, True))

	print("Response")
	pprint(response.get_json())
