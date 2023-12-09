.PHONY: all init build install clean test_publish publish

all: init build install

init:
	pip3 install -r requirements.txt

build:
	python3 -m build

clean:
	rm -rf ./dist

install:
	pip3 install .

test_publish:
	python3 -m twine upload --repository testpypi dist/*

publish:
	python3 -m twine upload --repository pypi dist/*
