SHELL := /bin/zsh
PYTHON := .venv/bin/python

.PHONY: setup download graph pilot web-data serve test

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	npm install
	npm run vendor

download:
	$(PYTHON) scripts/download_data.py

graph:
	scripts/build_osrm_graph.sh

pilot:
	$(PYTHON) scripts/run_pilot.py --district Dhaka

web-data:
	$(PYTHON) scripts/export_web_data.py

serve: web-data
	$(PYTHON) scripts/serve_app.py

test:
	$(PYTHON) -m unittest discover -s tests -v
