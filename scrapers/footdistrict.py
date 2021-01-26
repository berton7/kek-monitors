import asyncio
from utils.tools import make_default_executable

from bs4 import BeautifulSoup
from fake_headers import Headers

from scrapers.base_scraper import BaseScraper


class Footdistrict(BaseScraper):
	def init(self):
		# website infos
		self.base_url = "https://footdistrict.com"
		self.endpoints = ["/en/sneakers.html"]

		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

		# max links to be monitored
		self.max_links = 5

	async def loop(self):
		# tasks will contain asynchronous tasks to be executed at once, asynchronously
		# in this case, they will contain the requests to the endpoints
		tasks = []  # List[Coroutine]
		# create a task for each endpoint
		for ep in self.endpoints:
			tasks.append(self.fetch(self.base_url +
                           ep, headers=self.headers_gen.generate()))

		# gather, execute all tasks
		responses = await asyncio.gather(*tasks)

		for response, text in responses:
			if not response:
				# error is already reported by NetworkUtils
				continue

			# BeautifulSoup can be used to parse html pages in a very convenient way
			soup = BeautifulSoup(text, "lxml")

			# parsing example. in this case we simply add the first self.max_links products.
			grid = soup.find("div", {"class": "category-products"})
			count = 0
			for row in grid.find_all("ul", {"class": "products-grid"}):
				for prod in row.find_all("li"):
					count += 1
					if count <= self.max_links:
						link = prod.a.get("href")
						if link not in self.links:
							self.links.append(link)
							self.general_logger.info(f"Found {link}")
							# if you want to send every link immediately (not recommended):
							# self.links = [link]
							# await self.add_links()
				break

		# at the end of each self.loop(), self.update_links() is called to send the links to the monitor, if they have changed since the previous loop


if __name__ == "__main__":
	make_default_executable(Footdistrict)
