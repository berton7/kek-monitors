from pprint import pprint

import pymongo
from kekmonitors.config import Config

if __name__ == "__main__":
	config = Config()

	db = pymongo.MongoClient(config.db_path)
	if config.db_name in db.list_database_names():
		print("Saved items:")
		for item in db["kekmonitors"]["items"].find({}, {"_id": 0}):
			pprint(item)

		print("Registered monitors:")
		for m in db["kekmonitors"]["register"]["monitors"].find({}, {"_id": 0}):
			pprint(m)

		print("Registered scrapers:")
		for m in db["kekmonitors"]["register"]["scrapers"].find({}, {"_id": 0}):
			pprint(m)
	else:
		print("Database does not exist")
