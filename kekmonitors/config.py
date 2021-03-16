import configparser
import copy
import enum
import os


@enum.unique
class COMMANDS(enum.Enum):
    PING = enum.auto()
    STOP = enum.auto()
    SET_SHOES = enum.auto()
    ADD_SHOES = enum.auto()
    GET_SHOES = enum.auto()
    GET_CONFIG = enum.auto()
    GET_WHITELIST = enum.auto()
    GET_BLACKLIST = enum.auto()
    GET_WEBHOOKS = enum.auto()
    SET_SPECIFIC_CONFIG = enum.auto()
    SET_SPECIFIC_WEBHOOKS = enum.auto()
    SET_SPECIFIC_BLACKLIST = enum.auto()
    SET_SPECIFIC_WHITELIST = enum.auto()
    SET_COMMON_CONFIG = enum.auto()
    SET_COMMON_WEBHOOKS = enum.auto()
    SET_COMMON_BLACKLIST = enum.auto()
    SET_COMMON_WHITELIST = enum.auto()

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
    MM_SET_MONITOR_SCRAPER_BLACKLIST = enum.auto()
    MM_SET_MONITOR_SCRAPER_WHITELIST = enum.auto()
    MM_SET_MONITOR_SCRAPER_WEBHOOKS = enum.auto()
    MM_SET_MONITOR_SCRAPER_CONFIG = enum.auto()
    MM_GET_MONITOR_SHOES = enum.auto()
    MM_GET_SCRAPER_SHOES = enum.auto()


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
    filename_directory_path = filename_path[: filename_path.rfind(os.path.sep)]
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
        path = os.path.sep.join([os.environ["HOME"], ".kekmonitors", "config"])
        config_path = os.path.sep.join([path, "config.cfg"])
        self.default_config_str = f"\
[GlobalConfig]\n\
socket_path = {os.environ['HOME']}/.kekmonitors/sockets\n\
log_path = {os.environ['HOME']}/.kekmonitors/logs\n\
db_name = kekmonitors\n\
db_path = mongodb://localhost:27017/\n\
\n\
[WebhookConfig]\n\
crash_webhook = \n\
provider = KekMonitors\n\
provider_icon = https://avatars0.githubusercontent.com/u/11823129?s=400&u=3e617374871087e64b5fde0df668260f2671b076&v=4\n\
timestamp_format = %d %b %Y, %H:%M:%S.%f\n\
embed_color = 255\n\
\n\
[OtherConfig]\n\
class_name =\n\
socket_name =\n\
\n\
[Options]\n\
add_stream_handler = True\n\
enable_config_watcher = True\n\
enable_webhooks = True\n\
loop_delay = 5\n\
max_last_seen = 2592000\n\
"
        get_file_if_exist_else_create(config_path, self.default_config_str)
        parser = configparser.RawConfigParser()
        self.parser = parser
        parser.read(config_path)
        self["GlobalConfig"]["config_path"] = path
        self["OtherConfig"]["class_name"] = ""
        self["OtherConfig"]["socket_name"] = ""

    def __getitem__(self, key: str) -> configparser.SectionProxy:
        return self.parser[key]


class LogConfig(Config):
    def __init__(self, config: Config = None):
        super().__init__()
        if config:
            self.parser = copy.deepcopy(config.parser)
        self.parser.add_section("LogConfig")
        self["LogConfig"]["stream_level"] = "logging.DEBUG"
        self["LogConfig"]["file_level"] = "logging.DEBUG"
