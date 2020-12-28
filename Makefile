all: lint typecheck test

lint:
	pylint buchfink/schema.py buchfink/account.py buchfink/serialization.py

typecheck:
	mypy buchfink

test:
	py.test
