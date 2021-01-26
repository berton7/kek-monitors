#!/bin/bash

python3 -m venv venv && source ./venv/bin/activate && pip install -r requirements.txt && python init.py && echo "Before running any monitor/scraper, make sure MongoDB is installed and running, source venv (\`source ./venv/bin/activate\`) and modify configs/monitors/webhooks.json to include a test webhook! For example: {\"MyWebsite\":{\"<your-webhook>\":{\"name\":\"test-webhook\"}}}"
