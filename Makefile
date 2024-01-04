all: lint typecheck test

lint:
	ruff buchfink tests
	pylint buchfink
	pycodestyle buchfink tests/*.py

typecheck:
	mypy buchfink tests/*.py

test:
	py.test

test-local:
	py.test -m 'not blockchain_data'

test-remote:
	py.test -m 'blockchain_data'

fast-lint-test:
	ruff buchfink tests
	py.test -m 'not blockchain_data' -x

format:
	ruff format buchfink tests
