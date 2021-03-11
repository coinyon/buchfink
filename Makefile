all: lint typecheck test

lint:
	pylint buchfink/schema.py buchfink/account.py buchfink/serialization.py buchfink/config.py buchfink/datatypes.py buchfink/cli.py buchfink/classification.py buchfink/report.py
	pycodestyle buchfink

typecheck:
	mypy buchfink

test:
	py.test

test-local:
	py.test -m 'not blockchain_data'
