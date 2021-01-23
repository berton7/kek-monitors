import asyncio
from datetime import datetime
from typing import Optional, Tuple

import tornado.httpclient
from tornado.curl_httpclient import CurlError
from typing import Dict
import pycurl
from utils.tools import get_logger


class NetworkUtils(object):
	def __init__(self, logger_name: str):
		self.asyncio_loop = asyncio.get_event_loop()
		tornado.httpclient.AsyncHTTPClient.configure(
			"tornado.curl_httpclient.CurlAsyncHTTPClient")
		self.client = tornado.httpclient.AsyncHTTPClient()
		self._last_modified_datetimes = {}  # type: Dict[str, datetime]
		# force a cache refresh after self.cache_timeout
		self.cache_timeout = 10 * 60
		# keep a copy of every page in memory, for when we receive 304
		self._cached_pages = {}  # type: Dict[str, str]
		# remember etags, sometimes some websites use them
		self._etags = {}  # type: Dict[str, str]

		for feature in pycurl.version.split(" "):
			if feature.find("brotli") != -1:
				self._has_brotli = True
				break
		else:
			self._has_brotli = False

		self.network_logger = get_logger(logger_name + ".NetworkUtils")
		self.network_logger.debug(f"Has brotli: {self._has_brotli}")

	async def fetch(self, url: str, use_cache=True, attempts=3, delay=2, *args, **kwargs) -> Tuple[Optional[tornado.httpclient.HTTPResponse], str]:
		'''Asynchronously fetch the url using a tornado client. If you want to fetch more urls at once use asyncio.gather(*tasks).\n
		You can pass arguments to client.fetch() using *args and **kwargs (e.g. if you need proxies you can call self.fetch like this:\n
		`self.fetch(url, headers=headers, proxy_host={your-proxy-host}, proxy_port={your-proxy-port})`'''
		total_attempts = attempts
		headers = kwargs.get("headers", {})
		# keep retrying the connection until we run out of attempts
		while attempts > 0:
			try:
				if_mod_since = None
				# if using cache and it has expired/timed out
				if use_cache and url in self._cached_pages and url in self._last_modified_datetimes:
					if (datetime.utcnow() - self._last_modified_datetimes[url]).seconds < self.cache_timeout:
						self.network_logger.debug(url + " is in cache, adding cache headers")
						if_mod_since = self._last_modified_datetimes[url]
						if url in self._etags:
							headers["if-none-match"] = self._etags[url]
					else:
						self.network_logger.info(url + " is in cache from more than " +
                                                    str(self.cache_timeout) + " seconds, refreshing the page.")
						self._cached_pages.pop(url)
						self._last_modified_datetimes.pop(url)

				# fix some possibly set headers from fake-headers
				headers["accept-encoding"] = "gzip, deflate"
				if self._has_brotli:
					headers["accept-encoding"] += ", br"
				headers.pop("pragma", None)
				headers.pop("Pragma", None)

				self.network_logger.debug(f"Getting {url}...")
				r = await self.client.fetch(url, if_modified_since=if_mod_since, raise_error=False, *args, **kwargs)
				self.network_logger.info(f"Got {url} with code {r.code}")
				if r.code == 599:
					self.network_logger.warning(
						f"Something happened while fetching {url}: {r.reason}")
					attempts -= 1
					if attempts:
						# sleep delay before retrying
						await asyncio.sleep(delay)
						continue
				elif r.code == 404:
					# usually this is what we want to do
					self.network_logger.debug("Not retrying on 404.")
					return r, r.body.decode()
				else:
					if use_cache:
						# if page was cached update it or just return it
						if r.code < 400 and r.code != 304:
							self._cached_pages[url] = r.body.decode()
							self._last_modified_datetimes[url] = datetime.utcnow()
							if "etag" in r.headers:
								self._etags[url] = r.headers["etag"]
						return r, self._cached_pages[url]
					else:
						return r, r.body.decode()

			except CurlError:
				self.network_logger.exception(f"Timed out while fetching {url}.")
				attempts -= 1
				if attempts:
					await asyncio.sleep(delay)
					continue

			except:
				self.network_logger.exception("Got exception:")
				await asyncio.sleep(delay)
				attempts -= 1
				if attempts:
					await asyncio.sleep(delay)
					continue

		self.network_logger.warning(
			f"Tried {total_attempts} but couldn't fetch {url}.")

		return self.__dict__.get("r", None), ""
