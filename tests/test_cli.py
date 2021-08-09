"Test buchfink cli app"
import logging
import os
import os.path

import pytest
from click.testing import CliRunner

from buchfink.cli import fetch_, init, report_, quote

logger = logging.getLogger(__name__)


@pytest.mark.blockchain_data
def test_run_on_ens_domain():
    "High level fetch+report integration test for adhoc accounts via ENS domain"
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(init)
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(fetch_, ['-e', 'coinyon.eth'])
        logger.debug('output of %s: %s', 'fetch', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(report_, ['-e', 'coinyon.eth', '--year', '2020'])
        logger.debug('output of %s: %s', 'report', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        # We should test json output here


def test_second_init_should_fail():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(init)
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(init)
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exit_code == 1


def test_init_and_subsequent_quote():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(init)
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(quote, ['ETH', '-b', 'USD'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exit_code == 0
        assert result.exception is None
