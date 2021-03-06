import asyncio
import json
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup
from fake_headers import Headers
from pyppeteer.launcher import launch
from pyppeteer.network_manager import Response
from pyppeteer.page import Page

from kekmonitors.base_monitor import BaseMonitor
from kekmonitors.config import Config
from kekmonitors.shoe_stuff import Shoe
from kekmonitors.utils.tools import make_default_executable


class Footdistrict(BaseMonitor):
    def init(self):
        # create a random headers generator, configured to generate random windows headers
        self.headers_gen = Headers(os="win", headers=True)

    async def async_init(self):
        self.browser = await launch()
        #  self.context = await self.browser.createIncognitoBrowserContext()
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
                f"{link}: got 307, waiting to redirect and stuff..."
            )
            try:
                response = await page.waitForResponse(
                    lambda res: res.url == link and res.status == 200,
                    {"timeout": 10000},
                )
                if response.ok:
                    self.network_logger.debug(
                        f"{link}: got redirection, waiting for it to finish loading..."
                    )
                    await page.waitForNavigation()
                    self.network_logger.debug(f"{link}: has loaded")
                    await asyncio.sleep(1)
                    # await page.setJavaScriptEnabled(False)
                    # await page.keyboard.press("Escape")
                else:
                    self.network_logger.warning(
                        f"{link}: failed to get: {response.status}"
                    )
            except:
                self.general_logger.exception(
                    f"{link} has failed to redirect. Current url: {response.url}, status: {response.status}, page url: {page.url}"
                )
        elif response.ok:
            self.network_logger.debug(f"{link}: got it with code {response.status}")

        return response

    async def loop(self):
        # get timestamp for all shoes seen since max_last_seen
        ts = datetime.utcnow().timestamp() - float(
            self.config["Options"]["max_last_seen"]
        )
        # get those shoes
        shoes = self.shoe_manager.find_shoes({"last_seen": {"$gte": ts}})
        if not shoes:
            shoe = Shoe()
            shoe.link = (
                "https://footdistrict.com/nike-air-max-95-ndstrkt-cz3591-001.html"
            )
            shoes.append(shoe)

        # tasks will contain asynchronous tasks to be executed at once asynchronously
        # in this case, they will contain the requests to the links
        tasks = []
        pages = []  # type: List[Page]
        for shoe in shoes:
            page = await self.context.newPage()
            pages.append(page)
            tasks.append(self.get_fd_page(shoe.link, page))

        # gather, execute all tasks
        responses = await asyncio.gather(*tasks)  # type: List[Response]
        self.network_logger.debug("Got all links")

        for shoe, page, response in zip(shoes, pages, responses):
            if not response.ok:
                self.general_logger.debug(
                    f"{shoe.link}: skipping parsing on code {response.code}"
                )
                continue

            text = await response.text()

            if len(text) < 1000:
                self.general_logger.warning(
                    f"Failed to get {shoe.link} (len of response: {len(text)})"
                )
                continue

            # BeautifulSoup can be used to parse html pages in a very convenient way
            soup = BeautifulSoup(text, "lxml")

            # create a Shoe object to hold information
            # parse all the page. for simplicity here we only get the name
            n = soup.find("meta", {"property": "og:title"})
            if n:
                shoe.name = n.get("content")
                # https://footdistrict.com/media/resize/500x333/catalog/product/p/r/producto_02_10_2063_4/adidas-rivalry-hi-x-star-wars-chewbacca-fx9290-0.webp
                # s.img_link = soup.find("div", {"id": "productos-ficha-item"}).find(
                # 	"img", {"class": "img-responsive lazyloaded"}).get("src")
                shoe.img_link = "https://i.imgur.com/UKwBVpg.png"
                for script in soup.find_all("script", {"type": "text/x-magento-init"}):
                    script_text = script.string
                    if script_text.find("jsonConfig") != -1:
                        script_json = json.loads(script_text)
                        options = script_json["[data-role=swatch-options]"][
                            "Magento_Swatches/js/swatch-renderer"
                        ]["jsonConfig"]["attributes"]["134"]["options"]
                        for opt in options:
                            sizename = opt["label"]
                            available = bool(opt["products"])
                            shoe.sizes[sizename] = {"available": available}
                        break

                else:
                    self.general_logger.warning("Couldn't find script -- skipping.")

            else:
                self.general_logger.warning(
                    "Couldn't find name meta property -- skipping."
                )

            # self.shoe_check takes the shoe, updates last_seen, checks for restocks, updates database, sends webhooks if enabled
            self.shoe_check(shoe)
            await page.close()


if __name__ == "__main__":
    custom_config = Config()
    custom_config["WebhookConfig"]["crash_webhook"] = "your-crash-webhook-here"
    make_default_executable(Footdistrict, custom_config)
