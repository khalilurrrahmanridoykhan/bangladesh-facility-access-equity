SHELL := /bin/zsh
PYTHON := .venv/bin/python

.PHONY: setup download graph pilot test

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

download:
	$(PYTHON) scripts/download_data.py

graph:
	scripts/build_osrm_graph.sh

pilot:
	$(PYTHON) scripts/run_pilot.py --district Dhaka

test:
	$(PYTHON) -m unittest discover -s tests -v

