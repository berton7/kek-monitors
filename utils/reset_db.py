from utils.shoe_manager import ShoeManager
from utils.tools import get_logger


if __name__ == "__main__":
	l = get_logger("Resetter")
	s = ShoeManager(l)
	c = input(
		f"Executing this file will destroy {s.db_name} (ALL WEBSITES, MONITORS, SCRAPERS) unrecoverably. Are you sure you want to proceed? (y/n) ")
	if c != "y":
		print("Exiting (no modifications have been made.)")
		exit(0)
	c = input("Are you sure? Last chance. (y/n) ")
	if c != "y":
		print("Exiting (no modifications have been made.)")
		exit(0)

	s._db.drop()
	print(f"Databases now available: {s._client.list_database_names()}")
	if s.db_name in s._client.list_database_names():
		print(f"Content of {s.db_name}: {list(s._db.find())}")
