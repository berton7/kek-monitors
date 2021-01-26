import enum

SOCKET_PATH = "./sockets"


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


class WEBHOOK_CONFIG(object):
	CRASH_WEBHOOK = ""
	DEFAULT_PROVIDER = "KekMonitors"
	DEFAULT_PROVIDER_ICON = "https://avatars0.githubusercontent.com/u/11823129?s=400&u=3e617374871087e64b5fde0df668260f2671b076&v=4"
	DEFAULT_TIMESTAMP_FORMAT = "%d %b %Y, %H:%M:%S.%f"
	DEFAULT_EMBED_COLOR = 255


class DB_CONFIG(object):
	DEFAULT_DB_NAME = "kekmonitors"
	DEFAULT_DB_PATH = "mongodb://localhost:27017/"
