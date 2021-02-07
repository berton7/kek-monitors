from kekmonitors.utils.shoe_manager import ShoeManager
from kekmonitors.utils.tools import get_logger
from pprint import pprint

if __name__ == "__main__":
	l = get_logger("Lister")
	s = ShoeManager(l)

	if s.db_name in s._client.list_database_names():
		for item in s._db.find({}, {"_id": 0}):
			pprint(item)
	else:
		print("Database does not exist")
