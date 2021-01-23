if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

from utils.shoe_manager import ShoeManager
from utils.tools import get_logger


if __name__ == "__main__":
	l = get_logger("Lister")
	s = ShoeManager(l)

	if s.db_name in s._client.list_database_names():
		for item in s._db.find({}, {"_id": 0}):
			print(item)
	else:
		print("Database does not exist")
