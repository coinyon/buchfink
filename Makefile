all: lint typecheck test

lint:
	pylint buchfink
	pycodestyle buchfink

typecheck:
	mypy buchfink

test:
	py.test

test-local:
	py.test -m 'not blockchain_data'
