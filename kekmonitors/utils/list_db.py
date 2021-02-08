from kekmonitors.config import LogConfig
from kekmonitors.utils.shoe_manager import ShoeManager
from kekmonitors.utils.tools import get_logger
from pprint import pprint

if __name__ == "__main__":
	config = LogConfig()
	config.name = "Lister"
	l = get_logger(config)
	s = ShoeManager()

	if s.db_name in s._client.list_database_names():
		for item in s._db.find({}, {"_id": 0}):
			pprint(item)
	else:
		print("Database does not exist")
