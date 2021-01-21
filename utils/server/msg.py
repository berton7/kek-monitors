from typing import Any, Dict, List, Optional, Tuple, Union
import pickle
import copy


class Message(object):
	def __init__(self, msg):
		if msg:
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

	def sanitize(self, o) -> Optional[Any]:
		if o is None:
			return None
		elif isinstance(o, dict):
			return self.sanitize_dict(o)
		elif isinstance(o, list):
			return self.sanitize_list(o)
		else:
			return o


	def sanitize_list(self, l: List[Any]) -> Optional[List[Any]]:
		obj = []
		for n, item in enumerate(l):
			s = self.sanitize(item)
			if s is None or (hasattr(s, "__len__") and not len(s)):
				pass
			else:
				obj.append(s)
		return obj if obj else None


	def sanitize_dict(self, d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		obj = copy.deepcopy(d)
		for key in d:
			s = self.sanitize(d[key])
			if s is None or (hasattr(s, "__len__") and not len(s)):
				obj.pop(key)
			else:
				obj[key] = s
		return obj if obj else None

	def get_json(self) -> Optional[Any]:
		return self.sanitize(self.__dict__)

	def get_bytes(self) -> bytes:
		return pickle.dumps(self.sanitize(self.__dict__))


class Cmd(Message):
	def __init__(self, msg: Union[bytes, Dict[str, Any]] = None):
		self.cmd = None
		self.payload = None
		super().__init__(msg)

	def has_valid_args(self, args: List[str]) -> Tuple[bool, Optional[List[str]]]:
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
	def __init__(self, msg: Union[bytes, Dict[str, Any]] = None):
		self.success = None
		self.reason = None
		self.payload = None
		super().__init__(msg)


def badResponse():
	return Response({"success": False, "reason": "Generic error"})


def okResponse():
	return Response({"success": True})
