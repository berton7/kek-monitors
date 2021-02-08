import os
import subprocess
import shlex
from kekmonitors.config import Config


def create_files(p, files):
	os.makedirs(p, exist_ok=True)
	for fn in files:
		complete_fn = os.path.sep.join([p, fn])
		if not os.path.isfile(complete_fn):
			with open(complete_fn, "w") as f:
				f.write("{}")


def create_config(p):
	create_files(p, ["whitelists.json", "blacklists.json",
                  "configs.json", "webhooks.json"])


if __name__ == "__main__":
	config_path = f"{os.environ['HOME']}/.config/kekmonitors"
	config_cfg_path = os.path.sep.join([config_path, "config.cfg"])
	os.makedirs(config_path, exist_ok=True)
	ret = subprocess.call(shlex.split(
		f"cp {__file__.replace('init.py', 'default_config.cfg')} {config_cfg_path}"))
	if ret:
		print(
			f"Failed to create static configuration file at {config_path} (exit code: {ret})")
		exit(1)
	print(f"Successfully created static config at: {config_path}")

	config = Config()
	create_files(config.socket_path, [])
	print(
		f"Successfully created socket path at: {config.socket_path}")

	cm_path = f"{config.config_path}/monitors"
	cs_path = f"{config.config_path}/scrapers"
	create_config(cm_path)
	print(f"Successfully created monitors configs at: {cm_path}")
	create_config(cs_path)
	print(f"Successfully created scrapers configs at: {cs_path}")

	ret = subprocess.call(shlex.split(f"sudo mkdir -p {config.log_path}"))
	if ret:
		print(
			f"Failed to create log directory at {config.log_path} (exit code: {ret})")
		exit(1)
	ret = subprocess.call(shlex.split(
		f"sudo chown -R {os.environ['USER']} {config.log_path}"))
	if ret:
		print(
			f"Failed to change log directory permissions at {config.log_path} (exit code: {ret})")
		exit(1)
	print(f"Successfully created log directory")

	print("\nSuccessfully initialized")
