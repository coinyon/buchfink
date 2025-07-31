all: format lint typecheck test-local-ff

lint:
	ruff check buchfink tests
	pylint buchfink
	pycodestyle buchfink tests/*.py

typecheck:
	mypy buchfink tests/*.py

test:
	py.test

test-local:
	py.test -m 'not blockchain_data'

test-local-x:
	py.test -m 'not blockchain_data' -x

test-local-ff:
	py.test -m 'not blockchain_data' --maxfail=5 --ff -v

test-remote:
	py.test -m 'blockchain_data'

format:
	ruff format buchfink tests
