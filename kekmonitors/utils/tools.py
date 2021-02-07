import argparse
import asyncio
import inspect
import logging
import logging.handlers
import os
from datetime import timezone
from typing import Optional

from kekmonitors.config import ERRORS, MonitorConfig, _Config

from kekmonitors.utils.server.msg import Cmd, Response, badResponse, okResponse


def get_logger(name: str, add_stream_handler: Optional[bool] = True, stream_level: int = logging.DEBUG, file_level: int = logging.DEBUG):
	'''Get preconfigured logger'''
	logger = logging.getLogger(name)
	logger.propagate = False
	logger.setLevel(logging.DEBUG)
	formatter = logging.Formatter(
		"[%(asctime)s] %(levelname)s: %(message)s")

	while logger.handlers:
		logger.handlers.pop()

	splitted_name = name.split(".")
	os.makedirs(os.path.sep.join(["logs", *splitted_name[:2]]), exist_ok=True)
	file_handler = logging.handlers.TimedRotatingFileHandler(filename=os.path.sep.join(
		["logs", *splitted_name[:2], "".join([splitted_name[-1], ".log"])]), when="midnight", interval=1, backupCount=7)
	file_handler.setLevel(file_level)
	file_handler.setFormatter(formatter)

	logger.addHandler(file_handler)

	if add_stream_handler:
		stream_handler = logging.StreamHandler()
		stream_handler.setLevel(stream_level)
		stream_handler.setFormatter(formatter)
		logger.addHandler(stream_handler)

	return logger


# https://stackoverflow.com/questions/31818050/round-number-to-nearest-integer
def proper_round(num, dec=0):
	num = str(num)[:str(num).index('.') + dec + 2]
	if num[-1] >= '5':
		return int(float(num[:-2 - (not dec)] + str(int(num[-2 - (not dec)]) + 1)))
	return int(float(num[:-1]))


def is_in_whitelist(full_name, whitelist, separator=","):
	'''For each string in whitelist, separate the string using separator and check if all splitted items are contained in full_name.\n
	This way for example you can check if either `air jordan 13` and/or `air high jordan 13` are in the whitelist=['air, jordan 13']'''
	if whitelist == []:
		return True
	for shoe_whitelist in whitelist:
		all_words_in_name = True
		for word_whitelist in shoe_whitelist.split(separator):
			if full_name.lower().find(word_whitelist) == -1:
				all_words_in_name = False
				break
		if all_words_in_name:
			return True

	return False


def utc_to_local(utc_dt):
	'''https://stackoverflow.com/questions/4563272/convert-a-python-utc-datetime-to-a-local-datetime-using-only-python-standard-lib'''
	return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


def chunks(lst, n):
	"""https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks?noredirect=1&lq=1\n
	Yield successive n-sized chunks from lst."""
	for i in range(0, len(lst), n):
		yield lst[i:i + n]


def make_default_executable(class_name, default_delay: int = 5):
	parser = argparse.ArgumentParser(
            description=f"Default executable for {class_name.__name__}, generated from utils.tools.make_default_executable")
	parser.add_argument("-d", "--delay", default=default_delay, type=int,
                     help=f"Specify a delay for the loop. (default: {default_delay})")
	parser.add_argument("--output", action=argparse.BooleanOptionalAction,
                     default=True,
                     help="Specify wether you want log output to the console or not. (note: this does not disable file log)",)
	args = parser.parse_args()
	if args.delay < 0:
		print(f"Cannot have a negative delay")
		return
	config = _Config()
	config.add_stream_handler = args.output
	class_name(config).start(args.delay)


def dump_error(logger: logging.Logger, response: Response):
	e = response.error.value
	if e:
		curframe = inspect.currentframe()
		calframe = inspect.getouterframes(curframe, 2)
		fn_name = calframe[1][3]
		log = f"{fn_name}: Error: {response.error.name}"
		if response.info:
			log += f"; info: {response.info}"
		if response.payload:
			log += f"; payload: {response.payload}"
		logger.warning(log)


async def make_request(socket_path: str, cmd: Cmd, expect_response=True) -> Response:
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
	r.error = ERRORS.SOCKET_DOESNT_EXIST
	return r
