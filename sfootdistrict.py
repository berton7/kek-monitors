import asyncio
from typing import List

from bs4 import BeautifulSoup
from fake_headers import Headers
from pyppeteer import launch
from pyppeteer.network_manager import Response
from pyppeteer.page import Page
from kekmonitors.utils.tools import make_default_executable

from kekmonitors.base_scraper import BaseScraper


class Footdistrict(BaseScraper):
	def init(self):
		# website infos
		self.base_url = "https://footdistrict.com"
		self.endpoints = ["/zapatillas/f/b/converse/"]

		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

		# max links to be monitored
		self.max_links = 5

	async def async_init(self):
		self.browser = await launch()
		# self.context = await self.browser.createIncognitoBrowserContext()
		self.context = self.browser

	async def on_async_shutdown(self):
		self.general_logger.debug("Shutting down browser...")
		await self.browser.close()
		self.general_logger.info("Browser has shut down...")

	async def get_fd_page(self, link: str, page: Page):
		await page.setExtraHTTPHeaders(self.headers_gen.generate())
		await page.setJavaScriptEnabled(True)
		self.network_logger.debug(f"{link}: getting...")
		response = await page.goto(link)
		if response.status == 307:
			self.network_logger.debug(
				f"{link}: got 307, waiting to redirect and stuff...")
			try:
				response = await page.waitForResponse(lambda res: res.url == link and res.status == 200, {"timeout": 10000})
				if response.ok:
					self.network_logger.debug(
						f"{link}: got redirection, waiting for it to finish loading...")
					await page.waitForNavigation()
					await asyncio.sleep(1)
					self.network_logger.debug(f"{link}: has loaded")
					# await page.setJavaScriptEnabled(False)
					# await page.keyboard.press("Escape")
				else:
					self.network_logger.warning(f"{link}: failed to get: {response.status}")
			except:
				self.general_logger.exception(
					f"{link} has failed to redirect. Current url: {response.url}, status: {response.status}, page url: {page.url}")
		elif response.ok:
			self.network_logger.debug(f"{link}: got it with code {response.status}")

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
		responses = await asyncio.gather(*tasks)   # type: List[Response]

		for link, page, response in zip(self.endpoints, pages, responses):
			if not response.ok:
				self.general_logger.debug(
					f"{link}: skipping parsing on code {response.status}")
				continue

			self.general_logger.debug("Getting content...")
			text = await response.text()
			self.general_logger.debug("Parsing content...")
			# BeautifulSoup can be used to parse html pages in a very convenient way
			soup = BeautifulSoup(text, "lxml")
			self.general_logger.debug("Content parsed...")

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
