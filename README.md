# KEK Monitors
This is a ready-to-use codebase onto which you can develop your custom sneakers monitors. It tries to handle everything for you: databases, discord webhooks, network connections etc, but you are encouraged to customize the source code to fit your needs.

Here scrapers and actual monitors are separated and working asynchronously, communicating through Unix sockets, leading to improved performance compared to having a single script doing everything synchronously. I also lied the basis for an api, so that you don't necessarily need to ssh into the server to activate monitors, but you can instead just use a rest api.

***NOTE: THERE ARE NO IMPORTANT ENDPOINTS IN THE CODE! THERE IS ONLY ONE SEMI-WORKING MONITOR PROVIDED AS AN EXAMPLE!***

If you have any questions please join the Discord server: https://discord.gg/76r8GJyeZZ

## Pre-requisites
* `Python 3` > 3.6
* `linux`: the monitors have been tested on Arch Linux and Ubuntu, but they should work on any other linux distro/WSL without any problem.
* `libcurl` compiled with async and possibly brotli support (look for `brotli` and `AsynchDNS` in `curl --version` features). Brotli support is recommended but often not shipped with packaged versions of curl; if you want to add support to it you can compile and install curl yourself with brotli, making sure with ```curl --version``` that you are getting the output from your compiled version, and reinstall `pycurl` with ```pip install pycurl --no-binary :all: --force-reinstall```
* [MongoDB](https://www.mongodb.org/dl/linux/) installed and running (get it from the link or from your package manager)

## Setup
```bash
# recommended: setup a virtualenvironment before actually installing to the system
python3 -m venv venv
source ./venv/bin/activate

# to install the package from the PyPI:
python3 -m pip install kekmonitors

# to install the package from source:
python3 -m pip install .

# if you want to try the examples:
# please make sure that `~/.local/bin/` is in your `$PATH`
cd demo
python3 -m pip install -r requirements.txt

# you're ready to go!
# remember to start MongoDB and perhaps setup a webhook in the configs so that you can see the notifications!
```

## Usage
If you want to quickly look at how monitors look like, take a look at the sample code [footdistrict_scraper.py](https://github.com/berton7/kek-monitors/blob/master/demo/footdistrict_scraper.py) and [footdistrict_monitor.py](https://github.com/berton7/kek-monitors/blob/master/demo/footdistrict_monitor.py)

Before using the ```kekmonitors.monitor_manager``` make sure you started the monitors/scraper at least once manually (this is needed to register it in the database):
```bash
# in a SSH screen session:
python3 <filename> [--delay n] --[[no-]output]
```

The recommended way to start and control monitors is via ```kekmonitors.monitor_manager```.
Assuming you are remotely working on a server via SSH and you want to start both a scraper and a monitor:
```bash
# in a SSH screen session:
python3 -m kekmonitors.monitor_manager

# in another SSH screen session:
python3 -m kekmonitors.monitor_manager_cli MM_ADD_MONITOR_SCRAPER --name <name> [--delay n] [other keyword arguments required by the monitor/scraper]
```
The monitor manager will automatically keep track of which monitors/scrapers are available and can notify if and when they crash; it also manages the config updates (**as soon as you change a file in the configs folder (```~/.kekmonitors/config``` by default) it notifies the interested monitors/scrapers**).

There is also an ```app.py``` that "bridges" between http and the monitor manager, which allows you to use a REST api to control the monitor manager:
```bash
# in a SSH screen session:
python3 -m kekmonitors.app
```
You can see the available endpoints by navigating to the root endpoint (by default: `http://localhost:8888/`).

```app.py``` is only used as an example, and you should not use it in "production" since it doesn't use any sort of authentication, so anyone who finds your server's ip address can very easily control your monitors.

## Configuration
Static configuration, like commands and global variables (```socket_path```), is contained in ```~/.config/kekmonitors/config.cfg``` by default (the default file is hardcoded in [config.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/config.py)); the "dynamic" configuration files instead, by default, are stored in ```~/.config/kekmonitors/monitors``` and ```~/.config/kekmonitors/scrapers```; every scraper and monitor looks for its corresponding entry in `blacklist.json`, `whitelist.json`, and a general not-yet-used `configs.json`. Here's an example blacklists.json:

```json
{
	"Footdistrict":
	[
		"some term",
		"another, term"
	],
	"AnotherWebsite":
	[
		"one more, term",
		"so many terms"
	]
}
```

More information on the syntax can be found in `kekmonitors.utils.tools.is_whitelist().`

The `webhooks.json` file can be used to add webhooks configuration, with support to optional customization:

```json
{
	"Footdistrict":
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

The default embed generation is found in [discord_embeds.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/utils/discord_embeds.py).

## How does it all work?
The project can be thought of as being divided into several big parts: scrapers, monitors, database manager, webhook manager, discord embeds, monitor manager+api. Obviously you can, and should, customize everything to suite your needs, but you probably want to start by writing the first scraper/monitor combo.

I've tried to write everything so that you can easily customize your own monitor/scraper without modifying the source code too much: if for example you want to add custom commands to your monitor, adding statistics for instance, you can just extend the ```COMMANDS``` class, then write a callback function which will handle the received command and that's it!

## Important: about NetworkUtils.fetch()
By default fetch has the option `use_cache` set to True. The cache in question is not the typical CDN cache (the hit/miss cache from cloudflare for example), which you typically try to avoid (you look for the miss) to have the most up to date page possible; it's HTTP cache, which is "activated" by the [if-modified-since](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-Modified-Since) and [etag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag) headers: when *this* cache is hit, the return code is 304 and the body is empty, which saves a huge amount of bandwidth; from what I tested this seems like a really good option since the response is almost entirely empty, saving up on proxy bandwidth and general costs, and it doesn't seem to impact performance (remember it's not CDN related, but purely HTTP related). NetworkUtils automatically manages the internal pages cache.

Anyway you can turn off this behavior with `use_cache=False` on each request, retrieving a full response each time.

## List of executables/useful scripts:
* [monitor_manager.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/monitor_manager.py): manages monitors and scrapers, can be used to talk to them via ```kekmonitors.monitor_manager_cli```
* [monitor_manager_cli.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/monitor_manager_cli.py): allows you to issue commands to the monitor manager
* [utils/list_db.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/utils/list_db.py): lists available items in the ```kekmonitors``` database
* [utils/reset_db.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/utils/reset_db.py): resets the ```kekmonitors``` database
* [utils/stop_moman.py](https://github.com/berton7/kek-monitors/blob/master/kekmonitors/utils/stop_moman.py): stops ```kekmonitors.monitor_manager```
