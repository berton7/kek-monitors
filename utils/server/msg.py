import enum
import json
import pickle
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple, Union

from configs.config import COMMANDS, ERRORS


class Message(object):
	'''Represents a message to be sent. It can be initialized with a json structure or bytes taken from a pickle.dumps of another message.\n
	Once you set all the member variables you need you convert the message to bytes with to_bytes()
	or access it as a json structure with to_json()'''

	def __init__(self, msg: Optional[Union[bytes, Dict[str, Any]]] = None):
		# update member variables by cycling through the first level of the json dict
		if isinstance(msg, bytes):
			try:
				j = json.loads(msg)    # type: Dict[str, Any]
				for key in self.__dict__:
					self.__dict__[key] = j.get(key, None)
			except:
				pass
		elif isinstance(msg, dict):
			for key in self.__dict__:
				self.__dict__[key] = msg.get(key, None)
		else:
			pass

	def get_json(self) -> Optional[Any]:
		'''Return a json representation of the message'''
		return self.__dict__

	def get_bytes(self) -> bytes:
		'''Return a bytes representation of the message'''
		return json.dumps(self.get_json()).encode("utf-8")


class Cmd(Message):
	'''Represents a command to be sent. It can be initialized with a json structure or bytes taken from a pickle.dumps of another message.\n'''

	def __init__(self, msg: Optional[Union[bytes, Dict[str, Any]]] = None):
		self.cmd = None  # type: Optional[int]
		self.payload = None  # type: Optional[Dict[str, Any]]
		super().__init__(msg)

	@property
	def cmd(self):
		if self.__cmd is not None:
			return COMMANDS(self.__cmd)
		else:
			return None

	@cmd.setter
	def cmd(self, cmd):
		if isinstance(cmd, COMMANDS):
			self.__cmd = cmd.value
		elif isinstance(cmd, int) or cmd is None:
			self.__cmd = cmd
		else:
			raise Exception(f"Tried to set cmd to unsupported value ({type(cmd)})")

	def has_valid_args(self, args: List[str]) -> Tuple[bool, Optional[List[str]]]:
		'''Checks if the payload in the cmd has all the required arguments.\n
		Returns (success, missing_arguments)'''
		if self.payload:
			missing = []
			for needed_arg in args:
				if needed_arg not in self.payload:
					missing.append(needed_arg)
			if missing:
				return False, missing
			else:
				return True, None
		return False, args


class Response(Message):
	'''Represents a response to a command. It can be initialized with a json structure or bytes taken from a pickle.dumps of another message.\n
	Success always has to be set. If it is false, a reason must be provided, otherwise it's gonna be just ignored.\n
	If you need to return data insert it into the payload'''

	def __init__(self, msg: Optional[Union[bytes, Dict[str, Any]]] = None):
		self.error = None  # type: Optional[int]
		self.info = None  # type: Optional[str]
		self.payload = None  # type: Optional[Dict[str, Any]]
		super().__init__(msg)

	@property
	def error(self):
		if self.__error is not None:
			return ERRORS(self.__error)
		else:
			return None

	@error.setter
	def error(self, error):
		if isinstance(error, ERRORS):
			self.__error = error.value
		elif isinstance(error, int) or error is None:
			self.__error = error
		else:
			raise Exception(f"Tried to set error to unsupported value ({type(error)})")

	@property
	def info(self):
		return self.__info

	@info.setter
	def info(self, info):
		if isinstance(info, str) or info is None:
			self.__info = info
		else:
			raise Exception(f"Tried to set info to unsupported value ({type(info)})")


def badResponse():
	'''Quickly create an unsuccessful response with a default error.'''
	r = Response()
	r.error = ERRORS.OTHER_ERROR
	return r


def okResponse():
	'''Quickly create a successful response'''
	r = Response()
	r.error = ERRORS.OK
	return r
