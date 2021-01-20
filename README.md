# Berton monitors v2
This is a ready-to-use codebase onto which you can develop your custom sneakers monitors. It tries to handle everything for you: databases, discord webhooks, network connections etc, but you are encouraged to customize the source code to fit your needs.

Here scrapers and actual monitors are separated and working asynchronously, communicating through Unix sockets, leading to improved performance compared to having a single script doing everything synchronously. I also lied the basis for an api, so that you don't necessarily need to ssh into the server to activate monitors, but you can instead just use a rest api.


## Pre-requisites
* `Python 3` > 3.5
* `linux`: the monitors have been tested on an Arch Linux installation for only a short amount of time unfortunately, but they should be able to run well and on any linux distribution. Windows is not officially supported, but if you really cannot/don't want to use linux, you should change the communication between monitors from Unix sockets to normal sockets, change, if needed, the default asyncio loop (I know sometimes it can give problems), and have a working dev-version of `libcurl`.
* `libcurl` compiled with async and possibly brotli support (look for `brotli` and `AsynchDNS` in `curl --version` features). Brotli support is recommended but often not shipped with packaged versions of curl; if you want to add support to it you can compile and install curl yourself with brotli, making sure with ```curl --version``` that you are getting the output from your compiled version, and reinstall `pycurl` with ```pip install pycurl --no-binary :all: --force-reinstall```

## Setup
```bash
# create and activate a virtual environment, optional but recommended
python3 -m venv venv 
source ./venv/bin/activate

# install requirements
python3 -m pip install -r requirements.txt

# setup the environment
./setup.sh
```

## Usage
If you write your monitors like the my_website.py examples you can run them like this:
```bash
# in a ssh screen session, start the scraper
python3 scrapers/my_website.py --delay n
# in another ssh screen session, start the monitor
python3 monitors/my_website.py --delay n
```
It doesn't really matter which one you start first; as soon as it starts the monitor tries to fetch links from the scraper, and any time the scraper finds new links it sends them to the monitor.

You can also remotely start them using the api and the monitor manager:
```bash
# in a ssh screen session, start the monitor manager
python3 monitor_manager.py
# in another ssh screen session, start the api
python3 app.py

# to start the my_website monitor and scraper:
curl http://{your-server-ip}:{api-port}/add -d '{"filename":"my_website", "class_name":"MyWebsite"}'
```
The provided api is only used as an example, and you should not use it in "production" since it doesn't currently use any sort of authentication, so anyone who finds your server's ip address can very easily control your monitors.

## Configuration
The configuration files can be found in the configs folder. Python related stuff, like commands and global variables (socket_path), is contained in `config.py`; every scraper and monitor has a `blacklist.json`, `whitelist.json`, and a general unused `configs.json` that are customized per-website. Every monitor/scraper, unless configured otherwise, generates a new empty entry when it doesn't find one, so it's pretty easy to understand how the config files generally work; anyway, here's an example blacklists.json:

```json
{
	"my_website": 
	[
		"some term",
		"another, term"
	],
	"another_website":
	[
		"one more, term",
		"so many terms"
	]
}
```

More information on the syntax can be found in `utils.tools.is_whitelist().`

Monitors also have a `webhooks.json` file to add webhooks, with support to optional customization:

```json
{
	"my_website": 
	{
		"https://discordapp.com/api/webhooks/your-webhook-here": {
                        "name": "Human readable name, not used at all in the code",
                        "custom": {
                                "provider": "your-provider-name",
                                "icon_url": "your-icon-url"
                        }
		},
		"https://discordapp.com/api/webhooks/another-webhook": {
                        "name": "A webhook with default customization"
		}
	}
}
```

## How does it all work?
The project can be thought of as being divided into several big parts: scrapers, monitors, database manager, webhook manager, discord embeds, monitor manager+api. Obviously you can, and should, customize everything to suite your needs, but you probably want to start by writing the first scraper/monitor combo.

There are only **two requirements**, needed to allow simple communication between the two and make everything work, that is they need to have the **same filename and class name**; what I would generally do is name the file after the website it should work with, and same thing for the class name (filename and class name don't necessarily need to be different).

You can get started by looking at the sample code `my_website.py` in [scrapers]() and [monitors]()

## About NetworkUtils.fetch()
By default fetch has the option `use_cache` set to True. The cache in question is not the typical CDN cache (the hit/miss cache from cloudflare for example), which you typically try to avoid (you look for the miss) to have the most up to date page possible; it's HTTP cache, which is "activated" by the [if-modified-since](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-Modified-Since) and [etag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag) headers: when *this* cache is hit, the return code is 304 and the body is empty, which saves a huge amount of bandwidth; from what I tested this seems like a really good option since the response is almost entirely empty, saving up on proxy bandwidth and general costs, and it doesn't seem to impact performance (remember it's not CDN related, but purely HTTP related). NetworkUtils automatically manages the internal pages cache.

Anyway you can turn off this behavior with `use_cache=False` on each request, retrieving a full response each time.
