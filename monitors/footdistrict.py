import asyncio
import json
from typing import List

from bs4 import BeautifulSoup
from fake_headers import Headers
from pyppeteer.launcher import launch
from pyppeteer.network_manager import Response
from pyppeteer.page import Page
from utils.shoe_stuff import Shoe
from utils.tools import make_default_executable

from monitors.base_monitor import BaseMonitor


class Footdistrict(BaseMonitor):
	def init(self):
		# create a random headers generator, configured to generate random windows headers
		self.headers_gen = Headers(os="win", headers=True)

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
		await page.goto(link)
		self.network_logger.debug(f"{link}: waiting to redirect and stuff...")
		response = await page.waitForResponse(lambda res: res.url == link and res.status == 200, {"timeout": 10000})
		if response.ok:
			# await page.waitForNavigation()
			self.network_logger.debug(f"{link}: has loaded")
			await page.setJavaScriptEnabled(False)
			await page.keyboard.press("Escape")
		else:
			self.network_logger.warning(f"{link}: failed to get: {response.status}")
		return response

	async def loop(self):
		# current links are contained in self.links
		if not self.links:
			self.links = [
				"https://footdistrict.com/nike-air-max-95-ndstrkt-cz3591-001.html"]
		self.general_logger.debug(f"Links are: {self.links}")

		# tasks will contain asynchronous tasks to be executed at once asynchronously
		# in this case, they will contain the requests to the links
		tasks = []
		pages = []  # type: List[Page]
		for link in self.links:
			page = await self.context.newPage()
			pages.append(page)
			tasks.append(self.get_fd_page(link, page))

		# gather, execute all tasks
		responses = await asyncio.gather(*tasks)  # type: List[Response]

		for link, page, response in zip(self.links, pages, responses):
			if not response.ok:
				self.general_logger.debug(
					f"{link}: skipping parsing on code {response.code}")
				continue

			text = await page.content()
			await page.close()
			if len(text) < 1000:
				self.general_logger.warning(
					f"Failed to get {link} (len of response: {len(text)})")
				continue

			# BeautifulSoup can be used to parse html pages in a very convenient way
			soup = BeautifulSoup(text, "lxml")

			# create a Shoe object to hold information
			s = Shoe()
			# parse all the page. for simplicity here we only get the name
			s.name = soup.find("meta", {"property": "og:title"}).get("content")
			s.link = link
			# https://footdistrict.com/media/resize/500x333/catalog/product/p/r/producto_02_10_2063_4/adidas-rivalry-hi-x-star-wars-chewbacca-fx9290-0.webp
			# s.img_link = soup.find("div", {"id": "productos-ficha-item"}).find(
			#	"img", {"class": "img-responsive lazyloaded"}).get("src")
			for script in soup.find_all("script", {"type": "text/x-magento-init"}):
				script_text = script.string
				if script_text.find("jsonConfig") != -1:
					script_json = json.loads(script_text)
					options = script_json["[data-role=swatch-options]"]["Magento_Swatches/js/swatch-renderer"]["jsonConfig"]["attributes"]["134"]["options"]
					for opt in options:
						sizename = opt["label"]
						available = bool(opt["products"])
						s.sizes[sizename] = {"available": available}
					break
			else:
				pass

			# append the shoe to self.shoes. ShoeManager will check for restocked sizes or new products just after this loop, in self.shoe_check()
			self.shoes.append(s)


if __name__ == "__main__":
	make_default_executable(Footdistrict)
