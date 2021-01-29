import asyncio
import os
from pprint import pprint

from configs.config import COMMANDS, SOCKET_PATH
from utils.server.msg import Cmd
from utils.tools import make_request

if __name__ == "__main__":
	cmd = Cmd()
	cmd.cmd = COMMANDS.MM_STOP_MONITOR_MANAGER
	pprint(asyncio.run(make_request(f"{SOCKET_PATH}/MonitorManager", cmd)).get_json())
