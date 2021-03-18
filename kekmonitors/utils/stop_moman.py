from kekmonitors.config import COMMANDS
from kekmonitors.monitor_manager_cli import send
from kekmonitors.comms.msg import Cmd

if __name__ == "__main__":
    cmd = Cmd()
    cmd.cmd = COMMANDS.MM_STOP_MONITOR_MANAGER
    send(cmd)
