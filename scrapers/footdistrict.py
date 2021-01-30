import asyncio
from typing import List

from bs4 import BeautifulSoup
from fake_headers import Headers
from pyppeteer import launch
from pyppeteer.network_manager import Response
from pyppeteer.page import Page
from utils.tools import make_default_executable

from scrapers.base_scraper import BaseScraper


class Footdistrict(BaseScraper):
	def init(self):
		# website infos
		self.base_url = "https://footdistrict.com"
		self.endpoints = ["/zapatillas/f/b/nike/"]

		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

		# max links to be monitored
		self.max_links = 5

	async def async_init(self):
		self.browser = await launch()
		self.context = await self.browser.createIncognitoBrowserContext()
		await self.context.newPage()

	async def on_async_shutdown(self):
		await self.browser.close()

	async def get_fd_page(self, link: str, page: Page):
		await page.setExtraHTTPHeaders(self.headers_gen.generate())
		await page.setJavaScriptEnabled(True)
		self.network_logger.debug(f"{link}: getting...")
		r = await page.goto(link)
		self.network_logger.debug(f"{link}: waiting to redirect and stuff...")
		response = await page.waitForResponse(lambda res: res.url == link and res.status <= 300, {"timeout": 10000})
		if response.ok:
			# await page.waitForNavigation()
			await asyncio.sleep(1.5)  # give the page some time to load
			self.network_logger.debug(f"{link}: has loaded")
			await page.setJavaScriptEnabled(False)
			await page.keyboard.press("Escape")
		else:
			self.network_logger.warning(f"{link}: failed to get: {response.status}")
		return response

	async def loop(self):
		# tasks will contain asynchronous tasks to be executed at once, asynchronously
		# in this case, they will contain the requests to the endpoints
		pages = []  # type: List[Page]
		tasks = []  # List[Coroutine]
		# create a task for each endpoint
		for ep in self.endpoints:
			page = await self.context.newPage()
			pages.append(page)
			tasks.append(self.get_fd_page(self.base_url + ep, page))

		# gather, execute all tasks
		responses = await asyncio.gather(*tasks)

		for link, page, response in zip(self.endpoints, pages, responses):
			if not response.ok:
				self.general_logger.debug(
					f"{link}: skipping parsing on code {response.code}")
				continue

			text = await page.content()
			# BeautifulSoup can be used to parse html pages in a very convenient way
			soup = BeautifulSoup(text, "lxml")

			# parsing example. in this case we simply add the first self.max_links products.
			grid = soup.find("ol", {"class": "product-items"})
			count = 0
			for prod in grid.find_all("li"):
				count += 1
				if count <= self.max_links:
					link = prod.a.get("href")
					if link not in self.links:
						self.links.append(link)
						self.general_logger.info(f"Found {link}")
						# if you want to send every link immediately (not recommended):
						# self.links = [link]
						# await self.add_links()
				else:
					break

			await page.close()
		pass
		# at the end of each self.loop(), self.update_links() is called to send the links to the monitor, if they have changed since the previous loop


if __name__ == "__main__":
	make_default_executable(Footdistrict)
