import argparse
import asyncio
import inspect
import logging
import logging.handlers
import os
import sys
from datetime import timezone
from typing import Dict, List

from kekmonitors.comms.msg import Cmd, Response, badResponse, okResponse
from kekmonitors.config import ERRORS, Config, LogConfig

if sys.version_info[1] < 9:

    class BooleanOptionalAction(argparse.Action):
        def __init__(
            self,
            option_strings,
            dest,
            default=None,
            type=None,
            choices=None,
            required=False,
            help=None,
            metavar=None,
        ):

            _option_strings = []
            for option_string in option_strings:
                _option_strings.append(option_string)

                if option_string.startswith("--"):
                    option_string = "--no-" + option_string[2:]
                    _option_strings.append(option_string)

            if help is not None and default is not None:
                help += f" (default: {default})"

            super().__init__(
                option_strings=_option_strings,
                dest=dest,
                nargs=0,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar,
            )

        def __call__(self, parser, namespace, values, option_string=None):
            if option_string in self.option_strings:
                setattr(namespace, self.dest, not option_string.startswith("--no-"))

        def format_usage(self):
            return " | ".join(self.option_strings)


def get_logger(config: LogConfig):
    """
    Get preconfigured logger.
    """
    logger = logging.getLogger(config["OtherConfig"]["socket_name"])
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")

    while logger.handlers:
        logger.handlers.pop()

    splitted_name = config["OtherConfig"]["socket_name"].split(".")
    log_path = Config()["GlobalConfig"]["log_path"]
    os.makedirs(os.path.sep.join([log_path, *splitted_name[:2]]), exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.sep.join(
            [log_path, *splitted_name[:2], "".join([splitted_name[-1], ".log"])]
        ),
        when="midnight",
        interval=1,
        backupCount=7,
    )
    file_handler.setLevel(eval(config["LogConfig"]["file_level"]))
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    if config["Options"]["add_stream_handler"] == "True":
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(eval(config["LogConfig"]["stream_level"]))
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def proper_round(num, dec=0):
    """
    Properly rounds a number.
    See https://stackoverflow.com/questions/31818050/round-number-to-nearest-integer
    """
    num = str(num)[: str(num).index(".") + dec + 2]
    if num[-1] >= "5":
        return int(float(num[: -2 - (not dec)] + str(int(num[-2 - (not dec)]) + 1)))
    return int(float(num[:-1]))


def is_in_whitelist(full_name: str, whitelist: str, separator: str = ",") -> bool:
    """
    For each string in whitelist, separate the string using separator and check if all splitted items are contained in full_name.
    This way for example you can check if either `air jordan 13` and/or `air high jordan 13` are in the `whitelist = ['air, jordan 13']`
    """
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
    """
    Convert a utc timezone in a local timezone. Previously used in cache
    https://stackoverflow.com/questions/4563272/convert-a-python-utc-datetime-to-a-local-datetime-using-only-python-standard-lib
    """
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


def chunks(lst, n):
    """
    Yield successive n-sized chunks from lst.
    https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks?noredirect=1&lq=1
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def make_default_executable(_class, config: Config = None):
    """
    Start the specified class with an optional config, adding support to default cli options
    (needed for the monitor manager). ***Needs to be inside `if __name__=="__main__":`***
    """
    if not config:
        config = Config()

    if sys.version_info[1] < 9:
        boolAction = BooleanOptionalAction  # type: ignore
    else:
        boolAction = argparse.BooleanOptionalAction
    parser = argparse.ArgumentParser(
        description=f"Default executable for {_class.__name__}, generated from utils.tools.make_default_executable"
    )
    parser.add_argument(
        "-d",
        "--delay",
        default=config["Options"]["loop_delay"],
        type=float,
        help=f"Specify a delay for the loop. (default: {config['Options']['loop_delay']})",
    )
    parser.add_argument(
        "--output",
        action=boolAction,
        default=True if config["Options"]["add_stream_handler"] == "True" else False,
        help="Specify wether you want log output to the console or not. (note: this does not disable file log)",
    )
    parser.add_argument(
        "--config-watcher",
        action=boolAction,
        default=True if config["Options"]["enable_config_watcher"] == "True" else False,
        help="Specify wether you want to add a config watcher or not",
    )
    parser.add_argument(
        "-r",
        "--register",
        action="store_const",
        const="register",
        help="Only register the monitor/scraper, without actually starting it.",
    )
    parser.add_argument(
        "--webhooks",
        action=boolAction,
        default=True if config["Options"]["enable_webhooks"] == "True" else False,
        help="Enable sending webhooks",
    )
    parser.add_argument(
        "--max-last-seen",
        default=config["Options"]["max_last_seen"],
        type=int,
        help=f"Specify the max_last_seen value for shoes. (default: {config['Options']['max_last_seen']})",
        dest="max_last_seen",
    )
    parser_args, unknown = parser.parse_known_args()
    if parser_args.register:
        _class(config)
        exit()
    if parser_args.delay < 0:
        print(f"Cannot have a negative delay")
        return
    if parser_args.delay < 0:
        print("Cannot have a negative last seen")
        return
    config["Options"]["add_stream_handler"] = str(parser_args.output)
    config["Options"]["loop_delay"] = str(parser_args.delay)
    config["Options"]["enable_config_watcher"] = str(parser_args.config_watcher)
    config["Options"]["enable_webhooks"] = str(parser_args.webhooks)
    config["Options"]["max_last_seen"] = str(parser_args.max_last_seen)
    kwargs = {}  # type: Dict[str, str]
    if len(unknown) % 2:
        print("Incorrect number of kwargs")
        exit(1)
    for index, term in enumerate(unknown):
        if not index % 2:
            if not term.startswith("--"):
                print('You must start every kwargs key with "--"')
                exit(1)
            kwargs[term[2:]] = unknown[1 + index]

    _class(config, **kwargs).start()


def dump_error(logger: logging.Logger, response: Response):
    """
    Checks if the response is an error and dumps a useful message to the logger.
    """
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
    """
    Send `cmd` to `socket_path` and return the response if `expect_response` is True, else `okResponse()`.
    """
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


def list_contains_find_item(l: List[str], s: str) -> bool:
    """
    Return wether the `list` contains `s` even as a substring.
    """
    for item in l:
        if item.find(s) != -1:
            return True
    else:
        return False


def get_file_if_exist_else_create(filename_path, content) -> str:
    """
    If the file at `filename_path` exists, simply return the content;
    else, create the directories recursively, write `content` to `filename_path`
    and return content.
    """
    filename_directory_path = filename_path[: filename_path.rfind(os.path.sep)]
    os.makedirs(filename_directory_path, exist_ok=True)
    if os.path.isfile(filename_path):
        with open(filename_path, "r") as rf:
            return rf.read()
    else:
        with open(filename_path, "w") as wf:
            wf.write(content)
        return content
