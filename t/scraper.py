import sys
from typing import Any, Dict, List

sys.path.append("/home/berton/src/kek-monitors")

from kekmonitors.shoe_stuff import Shoe
from kekmonitors.base_scraper import BaseScraper
from kekmonitors.utils.tools import is_in_whitelist, make_default_executable
import random


class Test(BaseScraper):
    def init(self, **kwargs):
        s1 = Shoe()
        s2 = Shoe()
        s3 = Shoe()
        s1.link = "asd"
        s2.link = "123"
        s3.link = "black"
        for s in (s1,s2,s3):
            self.check_shoe(s)

    async def loop(self):
        pass


if __name__ == "__main__":
    make_default_executable(Test)
