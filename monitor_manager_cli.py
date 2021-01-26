import asyncio
import sys
from pprint import pprint

from configs.config import COMMANDS, SOCKET_PATH
from utils.server.msg import *
from utils.tools import make_request

if __name__ == "__main__":
	args = sys.argv
	if len(args) < 2:
		print("Usage: python monitor_manager_cli.py <cmd> [payload]")
		print(f"To list available commands: python {args[0]} --list-cmd")
		exit(1)
	if args[1] == "--list-cmd":
		for key in COMMANDS.__dict__:
			try:
				COMMANDS[key]
				print(key)
			except:
				pass
		exit(0)
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

	print("E:", response.error.name)
	if response.info:
		print("Info:", response.info)
	if response.payload:
		pprint(response.payload)
