import pymongo

from kekmonitors.config import Config

if __name__ == "__main__":
    config = Config()
    c = input(
        f"Executing this file will destroy {config['GlobalConfig']['db_name']} (ALL WEBSITES, MONITORS, SCRAPERS) unrecoverably. Are you sure you want to proceed? (y/n) "
    )
    if c != "y":
        print("Exiting (no modifications have been made.)")
        exit(0)
    c = input("Are you sure? Last chance. (y/n) ")
    if c != "y":
        print("Exiting (no modifications have been made.)")
        exit(0)

    root_db = pymongo.MongoClient(config["GlobalConfig"]["db_path"])
    db = root_db[config["GlobalConfig"]["db_name"]]
    for collection in db.list_collection_names():
        db[collection].drop()

    print("Done!")
