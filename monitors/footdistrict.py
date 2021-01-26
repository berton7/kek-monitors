import asyncio
from utils.tools import make_default_executable

from bs4 import BeautifulSoup
from fake_headers import Headers
from utils.shoe_stuff import Shoe

from monitors.base_monitor import BaseMonitor
import json


class Footdistrict(BaseMonitor):
	def init(self):
		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

	async def loop(self):
		# current links are contained in self.links
		if not self.links:
			self.links = [
				"https://footdistrict.com/en/adidas-rivalry-hi-x-star-wars-chewbacca-fx9290.html"]
		self.general_logger.debug(f"Links are: {self.links}")

		# tasks will contain asynchronous tasks to be executed at once asynchronously
		# in this case, they will contain the requests to the links
		tasks = []
		for link in self.links:
			tasks.append(self.fetch(link, headers=self.headers_gen.generate()))

		# gather, execute all tasks
		r = await asyncio.gather(*tasks)

		for link, pack in zip(self.links, r):
			response, text = pack
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
			s.link = link
			s.img_link = soup.find("a", {"id": "zoom1"}).find(
				"img", {"cloudzoom"}).get("src")
			for script in soup.find_all("script", {"type": "text/javascript"}):
				if script.string:
					if script.string.find("var spConfig") != -1:
						firststr = ".Config("
						script_t = script.string
						fi = script_t.find(firststr) + len(firststr)
						li = script_t.find(");")
						spConfig = script_t[fi:li]
						spConfig = json.loads(spConfig)
						for size in spConfig["attributes"]["134"]["options"]:
							sizename = size["label"]
							index = sizename.find(" * Not available")
							available = index == -1
							if not available:
								sizename = sizename[:index]
							s.sizes[sizename] = {"available": available}
			else:
				pass

			# append the shoe to self.shoes. ShoeManager will check for restocked sizes or new products just after this loop, in self.shoe_check()
			self.shoes.append(s)


if __name__ == "__main__":
	make_default_executable(Footdistrict)
