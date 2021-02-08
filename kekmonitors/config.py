import configparser
import enum
import logging
import os


@enum.unique
class COMMANDS(enum.Enum):
	PING = enum.auto()
	STOP = enum.auto()
	SET_LINKS = enum.auto()
	ADD_LINKS = enum.auto()
	GET_LINKS = enum.auto()
	SET_CONFIG = enum.auto()
	GET_CONFIG = enum.auto()
	SET_WHITELIST = enum.auto()
	GET_WHITELIST = enum.auto()
	SET_BLACKLIST = enum.auto()
	GET_BLACKLIST = enum.auto()
	SET_WEBHOOKS = enum.auto()
	GET_WEBHOOKS = enum.auto()

	MM_ADD_MONITOR = enum.auto()
	MM_ADD_SCRAPER = enum.auto()
	MM_ADD_MONITOR_SCRAPER = enum.auto()
	MM_STOP_MONITOR = enum.auto()
	MM_STOP_SCRAPER = enum.auto()
	MM_STOP_MONITOR_SCRAPER = enum.auto()
	MM_STOP_MONITOR_MANAGER = enum.auto()
	MM_GET_MONITOR_STATUS = enum.auto()
	MM_GET_SCRAPER_STATUS = enum.auto()
	MM_GET_MONITOR_SCRAPER_STATUS = enum.auto()
	MM_SET_MONITOR_CONFIG = enum.auto()
	MM_GET_MONITOR_CONFIG = enum.auto()
	MM_SET_MONITOR_WHITELIST = enum.auto()
	MM_GET_MONITOR_WHITELIST = enum.auto()
	MM_SET_MONITOR_BLACKLIST = enum.auto()
	MM_GET_MONITOR_BLACKLIST = enum.auto()
	MM_SET_MONITOR_WEBHOOKS = enum.auto()
	MM_GET_MONITOR_WEBHOOKS = enum.auto()
	MM_SET_SCRAPER_CONFIG = enum.auto()
	MM_GET_SCRAPER_CONFIG = enum.auto()
	MM_SET_SCRAPER_WHITELIST = enum.auto()
	MM_GET_SCRAPER_WHITELIST = enum.auto()
	MM_SET_SCRAPER_BLACKLIST = enum.auto()
	MM_GET_SCRAPER_BLACKLIST = enum.auto()
	MM_SET_SCRAPER_WEBHOOKS = enum.auto()
	MM_GET_SCRAPER_WEBHOOKS = enum.auto()


@enum.unique
class ERRORS(enum.Enum):
	OK = 0

	SOCKET_DOESNT_EXIST = enum.auto()
	SOCKET_COULDNT_CONNECT = enum.auto()
	SOCKET_TIMEOUT = enum.auto()

	MONITOR_DOESNT_EXIST = enum.auto()
	SCRAPER_DOESNT_EXIST = enum.auto()
	MONITOR_NOT_REGISTERED = enum.auto()
	SCRAPER_NOT_REGISTERED = enum.auto()

	UNRECOGNIZED_COMMAND = enum.auto()
	BAD_PAYLOAD = enum.auto()
	MISSING_PAYLOAD = enum.auto()
	MISSING_PAYLOAD_ARGS = enum.auto()

	MM_COULDNT_ADD_MONITOR = enum.auto()
	MM_COULDNT_ADD_SCRAPER = enum.auto()
	MM_COULDNT_ADD_MONITOR_SCRAPER = enum.auto()
	MM_COULDNT_STOP_MONITOR = enum.auto()
	MM_COULDNT_STOP_SCRAPER = enum.auto()
	MM_COULDNT_STOP_MONITOR_SCRAPER = enum.auto()

	OTHER_ERROR = enum.auto()
	UNKNOWN_ERROR = enum.auto()


# needed to avoid circular import
def get_file_if_exist_else_create(filename_path, content) -> str:
	filename_directory_path = filename_path[:filename_path.rfind(os.path.sep)]
	os.makedirs(filename_directory_path, exist_ok=True)
	if os.path.isfile(filename_path):
		with open(filename_path, "r") as rf:
			return rf.read()
	else:
		with open(filename_path, "w") as wf:
			wf.write(content)
		return content


class Config(object):
	def __init__(self):
		path = os.path.sep.join([os.environ['HOME'], ".kekmonitors", "config"])
		config_path = os.path.sep.join([path, "config.cfg"])
		default_config_str = f"\
[GlobalConfig]\n\
socket_path = {os.environ['HOME']}/.kekmonitors/sockets\n\
log_path = {os.environ['HOME']}/.kekmonitors/logs\n\
db_name = kekmonitors\n\
db_path = mongodb://localhost:27017/\n\
\n\
[DefaultBaseConfig]\n\
name = \n\
crash_webhook = \n\
provider = KekMonitors\n\
provider_icon = https://avatars0.githubusercontent.com/u/11823129?s=400&u=3e617374871087e64b5fde0df668260f2671b076&v=4\n\
timestamp_format = %d %b %Y, %H:%M:%S.%f\n\
embed_color = 255\n\
add_stream_handler = True\n\
loop_delay = 5\n"
		get_file_if_exist_else_create(config_path, default_config_str)
		parser = configparser.RawConfigParser()
		parser.read(config_path)
		parser.set("GlobalConfig", "config_path", path)

		self.config_path = parser.get("GlobalConfig", "config_path")
		self.socket_path = parser.get("GlobalConfig", "socket_path")
		self.log_path = parser.get("GlobalConfig", "log_path")
		self.db_name = parser.get("GlobalConfig", "db_name")
		self.db_path = parser.get("GlobalConfig", "db_path")

		self.name = parser.get("DefaultBaseConfig", "name")
		self.crash_webhook = parser.get("DefaultBaseConfig", "crash_webhook")
		self.provider = parser.get("DefaultBaseConfig", "provider")
		self.provider_icon = parser.get("DefaultBaseConfig", "provider_icon")
		self.timestamp_format = parser.get("DefaultBaseConfig", "timestamp_format")
		self.embed_color = parser.get("DefaultBaseConfig", "embed_color")
		self.add_stream_handler = parser.get(
			"DefaultBaseConfig", "add_stream_handler")
		self.loop_delay = parser.get("DefaultBaseConfig", "loop_delay")


class LogConfig(Config):
	def __init__(self, config: Config = None):
		if config is not None:
			for key in config.__dict__:
				self.__dict__[key] = config.__dict__[key]
		else:
			super().__init__()

		self.stream_level = logging.DEBUG
		self.file_level = logging.DEBUG
