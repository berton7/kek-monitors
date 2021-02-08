import os
from kekmonitors.config import GlobalConfig
import subprocess
import shlex


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
	create_files(GlobalConfig.socket_path, [])
	print(f"Successfully created socket path {GlobalConfig.socket_path}")

	cm_path = f"{GlobalConfig.config_path}/monitors"
	cs_path = f"{GlobalConfig.config_path}/scrapers"
	create_config(cm_path)
	print(f"Successfully created monitors configs at :{cm_path}")
	create_config(cs_path)
	print(f"Successfully created scrapers configs at :{cs_path}")

	ret = subprocess.call(shlex.split("sudo mkdir -p /var/log/kekmonitors"))
	if ret:
		print(f"Failed to create log directory (exit code: {ret})")
		exit(1)
	ret = subprocess.call(shlex.split(
		f"sudo chown -R {os.environ['USER']} /var/log/kekmonitors"))
	if ret:
		print(f"Failed to change log directory permissions (exit code: {ret})")
		exit(1)
	print(f"Successfully created log directory")

	print("Successfully initialized")
