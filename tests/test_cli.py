'Buchfink cli app integration tests'
import logging
import os
import os.path

import pytest
from click.testing import CliRunner

from buchfink.cli import buchfink, init

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def remove_buchfink_config_envvar(monkeypatch):
    monkeypatch.delenv("BUCHFINK_CONFIG", raising=False)
    yield


@pytest.mark.blockchain_data
def test_run_on_ens_domain():
    "High level fetch+report integration test for adhoc accounts via ENS domain"
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(buchfink, ['init'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['fetch', '-e', 'coinyon.eth'])
        logger.debug('output of %s: %s', 'fetch', result.output)
        assert result.exception is None
        assert result.exit_code == 0

        assert os.path.exists(os.path.join(d, 'trades/coinyon.eth.yaml'))
        assert os.path.exists(os.path.join(d, 'actions/coinyon.eth.yaml'))
        assert os.path.exists(os.path.join(d, 'balances/coinyon.eth.yaml'))

        result = runner.invoke(buchfink, ['report', '-e', 'coinyon.eth', '--year', '2020'])
        logger.debug('output of %s: %s', 'report', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        # We should test json output here


def test_second_init_should_fail():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(buchfink, ['init'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['init'])
        logger.warning('output of %s: %s', 'init', result.output)
        assert result.exit_code == 1


def test_init_and_subsequent_quote():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(buchfink, ['init'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['quote', 'ETH', '-b', 'USD'])
        logger.debug('output of %s: %s', 'quote', result.output)
        if result.exception:
            logger.exception(result.exception)
            raise result.exception
        assert result.exception is None
        assert result.exit_code == 0
