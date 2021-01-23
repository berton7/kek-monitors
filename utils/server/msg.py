import enum
import pickle
from typing import Any, Dict, List, Optional, Tuple, Union

from configs.config import COMMANDS

# sanitize functions remove any unneeded data from an object (e.g. None, empty lists/dicts)


def sanitize(o) -> Optional[Any]:
	if o is None:
		return None
	elif isinstance(o, dict):
		return sanitize_dict(o)
	elif isinstance(o, list):
		return sanitize_list(o)
	else:
		return o


def sanitize_list(l: List[Any]) -> Optional[List[Any]]:
	obj = []
	for item in l:
		# try to sanitize the item
		s = sanitize(item)
		# if the item is None or is empty:
		if s is None:
			# do nothing, else:
			pass
		else:
			# keep it, it's important!
			obj.append(s)
	return obj


def sanitize_dict(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	obj = {}
	for key in d:
		# try to sanitize the value
		s = sanitize(d[key])
		# if the item is None or is empty:
		if s is None:
			# do nothing, else:
			pass
		else:
			# keep it, it's important!
			obj[key] = s
	return obj


class Message(object):
	'''Represents a message to be sent. It can be initialized with a json structure or bytes taken from a pickle.dumps of another message.\n
	Once you set all the member variables you need you convert the message to bytes with to_bytes()
	or access it as a json structure with to_json()'''

	def __init__(self, msg: Optional[Union[bytes, Dict[str, Any]]] = None):
		# update member variables by cycling through the first level of the json dict
		if isinstance(msg, bytes):
			try:
				j = pickle.loads(msg)
				for key in j:
					if key in self.__dict__:
						self.__dict__[key] = j[key]
			except:
				pass
		elif isinstance(msg, dict):
			for key in msg:
				if key in self.__dict__:
					self.__dict__[key] = msg[key]
		else:
			pass

	def get_json(self) -> Optional[Any]:
		'''Return a json representation of the message'''
		return sanitize(self.__dict__)

	def get_bytes(self) -> bytes:
		'''Return a bytes representation of the message (using pickle)'''
		return pickle.dumps(self.get_json())


class Cmd(Message):
	'''Represents a command to be sent. It can be initialized with a json structure or bytes taken from a pickle.dumps of another message.\n'''

	def __init__(self, msg: Optional[Union[bytes, Dict[str, Any]]] = None):
		self.cmd = None  # type: Optional[int]
		self.payload = None  # type: Optional[Dict[str, Any]]
		super().__init__(msg)

	@property
	def cmd(self):
		try:
			return COMMANDS(self.__cmd)
		except ValueError:
			return self.__cmd

	@cmd.setter
	def cmd(self, cmd):
		if isinstance(cmd, enum.Enum):
			self.__cmd = cmd.value
		else:
			self.__cmd = cmd

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
		self.success = None  # type: Optional[bool]
		self.reason = None  # type: Optional[str]
		self.payload = None  # type: Optional[Dict[str, Any]]
		super().__init__(msg)


def badResponse():
	'''Quickly create an unsuccessful response with a default error.'''
	return Response({"success": False, "reason": "Generic error"})


def okResponse():
	'''Quickly create a successful response'''
	return Response({"success": True})
