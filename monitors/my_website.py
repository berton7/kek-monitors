if __name__ == "__main__":
	import os
	import sys
	sys.path.insert(0, os.path.abspath(
		os.path.join(os.path.dirname(__file__), '..')))

import argparse
import asyncio

from bs4 import BeautifulSoup
from fake_headers import Headers
from utils.shoe_stuff import Shoe

from monitors.base_monitor import BaseMonitor


class MyWebsite(BaseMonitor):

	def get_filename(self):
		'''YOU MUST OVERRIDE ME!!! Needed to get the correct filename.'''
		# take current path, split, get last element (=filename), remove ".py"
		return __file__.split(os.path.sep)[-1][:-3]

	def init(self):
		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

	async def loop(self):
		# current links are contained in self.links
		self.general_logger.debug(f"Links are: {self.links}")

		# tasks will contain asynchronous tasks to be executed at once asynchronously
		# in this case, they will contain the requests to the links
		tasks = []
		for link in self.links:
			tasks.append(self.fetch(self.client, link,
                           headers=self.headers_gen.generate()))

		# gather, execute all tasks
		r = await asyncio.gather(*tasks)

		for response, text in r:
			if not response:
				# error is already reported by NetworkUtils
				continue
			if response.code >= 400:
				self.general_logger.debug(
					f"{response.effective_url}: skipping parsing on code {response.code}")
				continue

			# BeautifulSoup can be used to parse html pages in a very convenient way
			soup = BeautifulSoup(text, "lxml")

			# create a Shoe object to hold information
			s = Shoe()
			# parse all the page. for simplicity here we only get the name
			s.name = soup.find("div", {"id": "product_text"}).h1.get_text()
			self.general_logger.debug(f"Checked {s.name}")

			# append the shoe to self.shoes. ShoeManager will check for restocked sizes or new products just after this loop, in self.shoe_check()
			self.shoes.append(s)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Sample monitor")
	default_delay = 10
	parser.add_argument("-d", "--delay", default=default_delay, type=int,
	                    help=f"Specify a delay for the loop. (default: {default_delay})")
	parser.add_argument("--output", action=argparse.BooleanOptionalAction,
                     default=True,
	                    help="Specify wether you want output to the console or not.",)
	args = parser.parse_args()
	if args.delay < 0:
		print(f"Cannot have a negative delay")
	MyWebsite(args.output).start(args.delay)
