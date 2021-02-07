import os
from kekmonitors.config import GlobalConfig


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

	print("Successfully initialized")
