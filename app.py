# This is an incomplete web app to access the monitor manager from the browser

import tornado.web
import tornado.ioloop
import asyncio
import pickle
from configs.config import *
import json


async def send_to_moman(message):
	'''Send a command to the monitor manager'''
	try:
		reader, writer = await asyncio.open_unix_connection(
			f"{SOCKET_PATH}/MonitorManager")
	except:
		return {"success": False, "reason": "Monitor manager not available"}

	writer.write(message)
	writer.write_eof()

	data = await reader.read()
	response = pickle.loads(data)
	print(f"{response}")

	writer.close()
	return response


class RootHandler(tornado.web.RequestHandler):
	async def get(self):
		self.write(
			{
				"available endpoints:": list(ep[0] for ep in endpoints)
			}
		)


class AddMonitorHandler(tornado.web.RequestHandler):
	async def post(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": ADD_MONITOR,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class AddScraperHandler(tornado.web.RequestHandler):
	async def post(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": ADD_SCRAPER,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class AddHandler(tornado.web.RequestHandler):
	async def post(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": ADD_MONITOR_SCRAPER,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class StopMonitorHandler(tornado.web.RequestHandler):
	async def delete(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": STOP_MONITOR,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class StopScraperHandler(tornado.web.RequestHandler):
	async def delete(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": STOP_SCRAPER,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class StopHandler(tornado.web.RequestHandler):
	async def delete(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": STOP_MONITOR_SCRAPER,
                            "payload": json.loads(self.request.body)})
		)

		if not r["success"]:
			self.set_status(400, r["msg"])
		self.write(r)


class MonitorStatusHandler(tornado.web.RequestHandler):
	async def get(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": GET_MONITOR_STATUS})
		)

		self.write(r)


class ScraperStatusHandler(tornado.web.RequestHandler):
	async def get(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": GET_SCRAPER_STATUS})
		)

		self.write(r)


class StatusHandler(tornado.web.RequestHandler):
	async def get(self):
		r = await send_to_moman(
			pickle.dumps({"cmd": GET_MONITOR_SCRAPER_STATUS})
		)

		self.write(r)


# add endpoints here
endpoints = [
	("/", RootHandler),
	("/monitors/add", AddMonitorHandler),
	("/scrapers/add", AddScraperHandler),
	("/add", AddHandler),
	("/monitors/stop", StopMonitorHandler),
	("/scrapers/stop", StopScraperHandler),
	("/stop", StopHandler),
	("/monitors/status", MonitorStatusHandler),
	("/scrapers/status", ScraperStatusHandler),
	("/status", StatusHandler),
]

if __name__ == "__main__":
	app = tornado.web.Application(endpoints)
	app.listen(8888)

	tornado.ioloop.IOLoop.current().start()
