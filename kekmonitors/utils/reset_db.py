import pymongo
from kekmonitors.config import GlobalConfig


if __name__ == "__main__":
	c = input(
		f"Executing this file will destroy {GlobalConfig.db_name} (ALL WEBSITES, MONITORS, SCRAPERS) unrecoverably. Are you sure you want to proceed? (y/n) ")
	if c != "y":
		print("Exiting (no modifications have been made.)")
		exit(0)
	c = input("Are you sure? Last chance. (y/n) ")
	if c != "y":
		print("Exiting (no modifications have been made.)")
		exit(0)

	root_db = pymongo.MongoClient(GlobalConfig.db_path)
	db = root_db[GlobalConfig.db_name]
	db["items"].drop()
	db["register"]["Monitors"].drop()
	db["register"]["Scrapers"].drop()

	print("Done!")
