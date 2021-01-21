import enum


@enum.unique
class COMMANDS(enum.Enum):
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


@enum.unique
class MOMAN_COMMANDS(enum.Enum):
	ADD_MONITOR = enum.auto()
	ADD_SCRAPER = enum.auto()
	ADD_MONITOR_SCRAPER = enum.auto()
	STOP_MONITOR = enum.auto()
	STOP_SCRAPER = enum.auto()
	STOP_MONITOR_SCRAPER = enum.auto()
	STOP_MONITOR_MANAGER = enum.auto()
	GET_MONITOR_STATUS = enum.auto()
	GET_SCRAPER_STATUS = enum.auto()
	GET_MONITOR_SCRAPER_STATUS = enum.auto()
	SET_CONFIG = enum.auto()
	GET_CONFIG = enum.auto()
	SET_WHITELIST = enum.auto()
	GET_WHITELIST = enum.auto()
	SET_BLACKLIST = enum.auto()
	GET_BLACKLIST = enum.auto()
	SET_WEBHOOKS = enum.auto()
	GET_WEBHOOKS = enum.auto()


SOCKET_PATH = "/tmp"
CRASH_WEBHOOK = ""
