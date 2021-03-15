import sys
from datetime import datetime

sys.path.append("/home/berton/src/kek-monitors")

import random

from kekmonitors.base_monitor import BaseMonitor
from kekmonitors.utils.tools import make_default_executable


class Test(BaseMonitor):
    async def loop(self):
        for shoe in self.shoe_manager.find_shoes(
            {
                "last_seen": {
                    "$gte": datetime.utcnow().timestamp()
                    - float(self.config["Options"]["max_last_seen"])
                }
            }
        ):
            print("Last seen:", datetime.fromtimestamp(shoe.last_seen))
            if not shoe.sizes:
                shoe.sizes = {random.choice(("12", "34", "13")): {"available": True}}
            else:
                shoe.sizes = {}
            self.shoe_check(shoe)


if __name__ == "__main__":
    make_default_executable(Test)
