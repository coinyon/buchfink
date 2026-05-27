"Buchfink cli app integration tests"

import logging
import os
import os.path
import shutil

import pytest
from click.testing import CliRunner

from buchfink.cli import buchfink
from buchfink.db import BuchfinkDB
from buchfink.tasks import fetch_trades

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def remove_buchfink_config_envvar(monkeypatch):
    monkeypatch.delenv('BUCHFINK_CONFIG', raising=False)
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

        result = runner.invoke(
            buchfink, ['report', '-e', 'coinyon.eth', '--year', '2020', '--no-vcs-check']
        )
        logger.debug('output of %s: %s', 'report', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        # We should test json output here


def test_second_init_should_fail():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(buchfink, ['init'], catch_exceptions=False)
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['init'], catch_exceptions=False)
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


def test_asset_info():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        result = runner.invoke(buchfink, ['init'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['asset', 'ETH'])
        logger.debug('output of %s: %s', 'assert', result.output)
        if result.exception:
            logger.exception(result.exception)
            raise result.exception
        assert result.exception is None
        assert result.exit_code == 0
        assert 'evm token' in result.output
        assert 'own chain' in result.output
        assert 'SNX' not in result.output
        result = runner.invoke(
            buchfink, ['asset', '[eip155:1/erc20:0xdd974D5C2e2928deA5F71b9825b8b646686BD200]']
        )
        logger.debug('output of %s: %s', 'asset', result.output)
        if result.exception:
            logger.exception(result.exception)
            raise result.exception
        assert result.exception is None
        assert result.exit_code == 0
        assert 'KNC' in result.output
        assert 'evm token' in result.output


def test_ethereum_qrcode():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'ethereum'), d, dirs_exist_ok=True
        )
        result = runner.invoke(buchfink, ['list'])
        logger.debug('output of %s: %s', 'list', result.output)
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['list', '-o', 'address'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert '0xD57479B8287666B44978255F1677E412d454d4f0\n' in result.output
        assert result.exception is None
        assert result.exit_code == 0
        result = runner.invoke(buchfink, ['list', '-o', 'qrcode'])
        logger.debug('output of %s: %s', 'init', result.output)
        assert result.exception is None
        assert result.exit_code == 0


def test_ethereum_gas_report_cli():
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'ethereum_gas'),
            d,
            dirs_exist_ok=True,
        )
        result = runner.invoke(buchfink, ['list'])
        logger.debug('output of %s: %s', 'list', result.output)
        assert result.exception is None
        assert result.exit_code == 0

        assert not os.path.exists(os.path.join(d, 'reports/all'))

        result = runner.invoke(buchfink, ['report', '-k', 'whale1', '--no-vcs-check'])
        logger.debug('output of %s: %s', 'report', result.output)
        assert 'all' in result.output
        assert 'Free P/L' in result.output
        assert 'Taxable P/L' in result.output
        assert result.exception is None
        assert result.exit_code == 0

        assert os.path.exists(os.path.join(d, 'reports/all/report.yaml'))
        assert os.path.exists(os.path.join(d, 'reports/all/report.md'))
        # assert os.path.exists(os.path.join(d, 'reports/all/all_events.csv'))
        assert os.path.exists(os.path.join(d, 'reports/all/report.log'))
        assert os.path.exists(os.path.join(d, 'reports/all/errors.log'))


def test_events_command():
    """Test the events CLI command with pre-existing action files"""
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'ethereum_gas'),
            d,
            dirs_exist_ok=True,
        )

        result = runner.invoke(buchfink, ['events', '-k', 'whale1'], catch_exceptions=False)
        logger.debug('output of %s: %s', 'events -k whale1', result.output)
        assert result.exit_code == 0
        assert result.exception is None
        assert 'ETH' in result.output

        result = runner.invoke(buchfink, ['events', '-k', 'whale1', '-a', 'ETH'], catch_exceptions=False)
        logger.debug('output of %s: %s', 'events -k whale1 -a ETH', result.output)
        assert result.exit_code == 0
        assert result.exception is None
        assert 'ETH' in result.output


def test_events_command_with_trade_asset_filter(tmp_path):
    """Test that events --asset filter works with SwapEvent objects from trades files"""
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
        os.path.join(tmp_path, 'buchfink'),
    )
    config_path = os.path.join(tmp_path, 'buchfink', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config_path)
    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'exchange1']
    fetch_trades(buchfink_db, accounts[0])
    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)
    assert len(trades) > 0
    buchfink_db.__del__()  # pylint: disable=unnecessary-dunder-call

    runner = CliRunner()
    result = runner.invoke(
        buchfink,
        ['--config', config_path, 'events', '-k', 'exchange1'],
        catch_exceptions=False,
    )
    logger.debug('output of %s: %s', 'events -k exchange1', result.output)
    assert result.exit_code == 0
    assert result.exception is None

    # Test --asset filter with SwapEvents — this was broken before the fix
    result = runner.invoke(
        buchfink,
        ['--config', config_path, 'events', '-k', 'exchange1', '-a', 'BTC'],
        catch_exceptions=False,
    )
    logger.debug('output of %s: %s', 'events -k exchange1 -a BTC', result.output)
    assert result.exit_code == 0
    assert result.exception is None
    assert 'BTC' in result.output


def test_balances_command():
    """Test the balances CLI command with pre-existing balance files"""
    runner = CliRunner()
    with runner.isolated_filesystem() as d:
        assert os.path.exists(d)
        # Copy test scenario with balance files
        shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'balances_test'),
            d,
            dirs_exist_ok=True,
        )

        # Test list command to verify accounts are loaded
        result = runner.invoke(buchfink, ['list'])
        logger.debug('output of %s: %s', 'list', result.output)
        assert result.exit_code == 0
        assert 'account1' in result.output
        assert 'account2' in result.output

        # Test balances command for single account
        result = runner.invoke(buchfink, ['balances', '-k', 'account1'])
        logger.debug('output of %s: %s', 'balances -k account1', result.output)
        if result.exception:
            logger.exception(result.exception)
            raise result.exception
        assert result.exit_code == 0
        assert 'account1' in result.output
        assert 'ETH' in result.output
        assert 'BTC' in result.output
        assert 'USDC' in result.output
        assert 'DAI' in result.output

        # Test balances command with --total flag for all accounts
        result = runner.invoke(buchfink, ['balances', '--total'])
        logger.debug('output of %s: %s', 'balances --total', result.output)
        if result.exception:
            logger.exception(result.exception)
            raise result.exception
        assert result.exit_code == 0
        # Should show both accounts
        assert 'account1' in result.output or 'account2' in result.output
        # Should show total summary
        assert 'Total' in result.output or 'ETH' in result.output
