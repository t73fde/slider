.PHONY: help clean py-dev build test

help:
	@echo "Allowed targets:"
	@echo "- help:   this text"
	@echo "- clean:  clean up a little bit"
	@echo "- py-dev: install all Python dependencies"
	@echo "- build:  build developement container"
	@echo "- test:   start full test run"

clean:
	rm -rf .tox htmlcov .coverage .mypy_cache

py-dev: 
	python ./setup.py develop

build:
	sudo docker build -t t73fde/slider -f docker/Dockerfile .

test:
	tox -e source,pylint,types,coverage
