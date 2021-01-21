# This is an incomplete web app to access the monitor manager from the browser

import tornado.web
import tornado.ioloop
import asyncio
import pickle
from configs.config import *
import json
from utils.server.msg import *


async def send_to_moman(cmd: Cmd):
	'''Send a command to the monitor manager'''
	try:
		reader, writer = await asyncio.open_unix_connection(
			f"{SOCKET_PATH}/MonitorManager")
	except:
		r = badResponse()
		r.reason = "Monitor manager not available"
		return r

	writer.write(cmd.get_bytes())
	writer.write_eof()

	data = await reader.read()
	response = Response(data)

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
		cmd = Cmd()
		cmd.cmd = ADD_MONITOR
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class AddScraperHandler(tornado.web.RequestHandler):
	async def post(self):
		cmd = Cmd()
		cmd.cmd = ADD_SCRAPER
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class AddHandler(tornado.web.RequestHandler):
	async def post(self):
		cmd = Cmd()
		cmd.cmd = ADD_MONITOR_SCRAPER
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class StopMonitorHandler(tornado.web.RequestHandler):
	async def delete(self):
		cmd = Cmd()
		cmd.cmd = STOP_MONITOR
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class StopScraperHandler(tornado.web.RequestHandler):
	async def delete(self):
		cmd = Cmd()
		cmd.cmd = STOP_SCRAPER
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class StopHandler(tornado.web.RequestHandler):
	async def delete(self):
		cmd = Cmd()
		cmd.cmd = STOP_MONITOR_SCRAPER
		cmd.payload = json.loads(self.request.body)
		r = await send_to_moman(cmd)

		if not r.success:
			self.set_status(400, r.reason)
		self.write(r.get_json())


class MonitorStatusHandler(tornado.web.RequestHandler):
	async def get(self):
		cmd = Cmd()
		cmd.cmd = GET_MONITOR_STATUS
		r = await send_to_moman(cmd)
		self.write(r.get_json())


class ScraperStatusHandler(tornado.web.RequestHandler):
	async def get(self):
		cmd = Cmd()
		cmd.cmd = GET_SCRAPER_STATUS
		r = await send_to_moman(cmd)
		self.write(r.get_json())


class StatusHandler(tornado.web.RequestHandler):
	async def get(self):
		cmd = Cmd()
		cmd.cmd = GET_MONITOR_SCRAPER_STATUS
		r = await send_to_moman(cmd)
		self.write(r.get_json())


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
