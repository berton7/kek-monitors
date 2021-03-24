from pprint import pprint

import pymongo

from kekmonitors.config import Config

if __name__ == "__main__":
    config = Config()

    db = pymongo.MongoClient(config["GlobalConfig"]["db_path"])
    if config["GlobalConfig"]["db_name"] in db.list_database_names():
        print("Saved items:")
        for collections_names in db[
            config["GlobalConfig"]["db_name"]
        ].list_collection_names():
            cls = db[config["GlobalConfig"]["db_name"]][collections_names]
            for item in cls.find({}, {"_id": 0}):
                pprint(item)
    else:
        print("Database does not exist")
