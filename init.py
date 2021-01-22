from configs.config import *
import os


def create_files(p, files):
	for fn in files:
		complete_fn = os.path.sep.join([p, fn])
		if not os.path.isfile(complete_fn):
			with open(complete_fn, "w") as f:
				f.write("{}")


def create_mc(p):
	create_files(p, ["whitelists.json", "blacklists.json",
                  "configs.json", "webhooks.json"])


def create_sc(p):
	create_files(p, ["whitelists.json", "blacklists.json",
                  "configs.json", "webhooks.json"])


if __name__ == "__main__":
	if not os.path.isdir(SOCKET_PATH):
		os.makedirs(SOCKET_PATH)
		print(f"Successfully created socket path {SOCKET_PATH}")

	cm_path = os.path.sep.join(["configs", "monitors"])
	cs_path = os.path.sep.join(["configs", "scrapers"])
	if not os.path.isdir(cm_path):
		os.mkdir(cm_path)
	create_mc(cm_path)
	print(f"Successfully created monitors configs")
	if not os.path.isdir(cs_path) or not os.listdir(cs_path):
		os.mkdir(cs_path)
	create_sc(cs_path)
	print(f"Successfully created scrapers configs")

	print("Successfully initialized")
