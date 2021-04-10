import asyncio
import enum
import os
from typing import Callable, Dict, Union

from kekmonitors.comms.msg import Cmd, Response, badResponse, okResponse
from kekmonitors.config import ERRORS, Config, LogConfig
from kekmonitors.utils.tools import get_logger


class Server(object):
    def __init__(self, config: Config, server_path: str):
        logconfig = LogConfig(config)
        logconfig["OtherConfig"]["socket_name"] += ".Server"
        self.server_logger = get_logger(logconfig)
        self.server_path = server_path
        socket_directory = self.server_path[: self.server_path.rfind(os.path.sep)]
        try:
            os.makedirs(socket_directory, exist_ok=True)
        except PermissionError:
            self.server_logger.exception(
                "Failed to create the socket directory. Please provide a directory where the current user has write permissions!"
            )
            exit(1)
        # init asyncio stuff
        self._asyncio_loop = asyncio.get_event_loop()
        self._server_task = self._asyncio_loop.create_task(self._init_server())

        self.cmd_to_callback = {}  # type: Dict[Union[int, enum.Enum], Callable]

    async def _init_server(self):
        """Initialise the underlying socket server, to allow communication between monitor/scraper."""
        self.server = await asyncio.start_unix_server(
            self._handle_msg, self.server_path
        )

        addr = self.server.sockets[0].getsockname()
        self.server_logger.debug(f"Serving on {addr}")

    async def _stop_serving(self, msg: Cmd):
        self.server_logger.info("Closing server...")
        self.server.close()
        await self.server.wait_closed()
        os.remove(self.server_path)
        self.server_logger.info("Server successfully closed.")
        return await self.on_server_stop()

    async def on_server_stop(self):
        return okResponse()

    async def _handle_msg(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming messages."""
        msg = Cmd(await reader.read())
        addr = writer.get_extra_info("peername")
        print_addr = addr if addr else "localhost"
        self.server_logger.debug(f"Received from {print_addr}")

        if msg.cmd in self.cmd_to_callback:
            self.server_logger.debug(f"Got cmd: {msg.cmd}")
            response = await self.cmd_to_callback[msg.cmd](msg)
        else:
            self.server_logger.warning(f"Got unrecognized command: {msg.cmd.value}")
            response = badResponse()
            response.error = ERRORS.UNRECOGNIZED_COMMAND

        writer.write(response.get_bytes())
        writer.write_eof()
        await writer.drain()

        self.server_logger.debug(f"Closed connection from {print_addr}")
        writer.close()

    async def make_request(
        self, socket_path: str, cmd: Cmd, expect_response: bool = True
    ) -> Response:
        if os.path.exists(socket_path):
            try:
                reader, writer = await asyncio.open_unix_connection(socket_path)
                writer.write(cmd.get_bytes())
                writer.write_eof()

                if expect_response:
                    r = Response(await reader.read())

                    writer.close()
                    return r
                return okResponse()
            except ConnectionRefusedError:
                self.server_logger.exception(
                    f"Couldn't connect to socket {socket_path}"
                )
                r = badResponse()
                r.error = ERRORS.SOCKET_COULDNT_CONNECT
                return r
        r = badResponse()
        r.error = ERRORS.SOCKET_DOESNT_EXIST
        return r
