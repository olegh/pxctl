init:
	pip install -r requirements.txt

build:
	python3 -m build

install:
	pip install .

test_publish:
	python3 -m twine upload --repository testpypi dist/*

publish:
	python3 -m twine upload --repository pypi dist/*
