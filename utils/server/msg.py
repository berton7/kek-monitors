import json
from typing import Any, Dict, Optional, Union
import pickle


class Message(object):
	def __init__(self, msg: Union[bytes, Dict[str, Any]] = None):
		self.msg = None
		self.msg_bytes = None

		if msg is not None:
			if isinstance(msg, bytes):
				r = self.to_json(msg)
				if r is not None:
					self.msg = r
					self.msg_bytes = msg
			else:
				r = self.to_bytes(msg)
				if r is not None:
					self.msg = msg
					self.msg_bytes = r

	def to_json(self, msg: bytes = None) -> Any:
		m = msg
		if msg is None:
			m = self.msg_bytes
		try:
			r = pickle.loads(m)
			json.dumps(r)
			return r
		except:
			return None

	def to_bytes(self, msg: Dict[str, Any] = None) -> Optional[bytes]:
		m = msg
		if msg is None:
			m = self.msg
		try:
			json.dumps(m)
			r = pickle.dumps(m)
			return r
		except:
			return None


class Cmd(Message):
	def __init__(self, msg: Union[bytes, Dict[str, Any]] = None):
		super().__init__(msg)
		self.cmd = self.get_cmd()
		self.payload = self.get_payload()

	def get_cmd(self):
		if self.msg:
			return self.msg.get("cmd", None)

	def get_payload(self):
		if self.msg:
			return self.msg.get("payload", None)

	def set_cmd(self, cmd: str):
		if self.msg:
			self.msg["cmd"] = cmd
		else:
			self.msg = {"cmd": cmd}

	def set_payload(self, payload: str):
		if self.msg:
			self.msg["payload"] = payload
		else:
			self.msg = {"payload": payload}


class Response(Message):
	def __init__(self, msg: Union[bytes, Dict[str, Any]] = None):
		super().__init__(msg)
		self.success = self.get_success()
		self.reason = self.get_reason()

	def get_success(self):
		if self.msg:
			return self.msg.get("success", None)

	def get_reason(self):
		if self.msg:
			return self.msg.get("reason", None)

	def get_payload(self):
		if self.msg:
			return self.msg.get("payload", None)

	def set_success(self, success: bool):
		if self.msg:
			if success and self.get_reason():
				self.msg.pop("reason")
			self.msg["success"] = success
		else:
			self.msg = {"success": success}

	def set_reason(self, reason: str):
		if self.msg:
			self.msg["reason"] = reason
		else:
			self.msg = {"reason": reason}

	def set_payload(self, payload: str):
		if self.msg:
			self.msg["payload"] = payload
		else:
			self.msg = {"payload": payload}


def badResponse():
	return Response({"success": False, "reason": "Generic error"})


def okResponse():
	return Response({"success": True})
