import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from kekmonitors.config import Config, LogConfig
import os

def _test_new_config(c):
	kcp = os.path.expanduser("~/.kekmonitors")
	if os.path.isdir(kcp):
		if os.system(f"rm -r {kcp}"):
			raise Exception(f"Failed to remove {kcp}")
	assert not os.path.isdir(kcp) and not os.path.isfile(kcp)

	c()
	assert os.path.isdir(kcp)

	if os.system(f"rm -r {kcp}"):
		raise Exception(f"Failed to delete new {kcp}")

def _test_existing_config_parser(c):
	def assert_config(section, key, value):
		kcp = os.path.expanduser("~/.kekmonitors")
		if os.path.isdir(kcp):
			if os.system(f"rm -r {kcp}"):
				raise Exception(f"Failed to remove {kcp}")
		assert not os.path.isdir(kcp) and not os.path.isfile(kcp)

		config = c()
		assert os.path.isdir(kcp)

		config.parser.set(section, key, value)
		with open(os.path.sep.join((config.config_path, "config.cfg")), "w") as wf:
			config.parser.write(wf)
		config = Config()
		v = config.parser.get(section, key)
		assert v == value

		if os.system(f"rm -r {kcp}"):
			raise Exception(f"Failed to delete new {kcp}")


	config = Config()
	d = config.__dict__
	d.pop("default_config_str")
	d.pop("parser")
	for section in d:
		for key in d[section]:
			assert_config(section, key, "test")


def test_new_config():
	_test_new_config(Config)


def test_existing_config():
	_test_existing_config_parser(Config)

def test_new_logconfig():
	_test_new_config(LogConfig)

def test_existing_logconfig():
	_test_existing_config_parser(LogConfig)
