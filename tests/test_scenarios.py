import os.path
import shutil

import pytest

from buchfink.db import BuchfinkDB
from buchfink.jobs import fetch_actions, fetch_trades
from buchfink.models import Account
from buchfink.report import run_report


def _fetch(buchfink_db: BuchfinkDB, account: Account) -> None:
    fetch_actions(buchfink_db, account)
    fetch_trades(buchfink_db, account)


def test_bullrun_full_taxes(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'exchange1']
    _fetch(buchfink_db, accounts[0])
    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)

    assert len(trades) == 2

    report_config = list(buchfink_db.get_all_reports())[0]
    result = run_report(buchfink_db, accounts, report_config)

    assert result['overview']['trade']['taxable'] == '15000'


def test_bullrun_no_taxes(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'exchange2']
    _fetch(buchfink_db, accounts[0])
    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)

    assert len(trades) == 2

    report_config = list(buchfink_db.get_all_reports())[0]
    result = run_report(buchfink_db, accounts, report_config)

    assert result['overview']['trade']['taxable'] == '0'
    assert result['overview']['trade']['free'] == '7000'


def test_ledger_actions_income(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_income']
    _fetch(buchfink_db, accounts[0])
    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)
    ledger_actions = buchfink_db.get_local_ledger_actions_for_account(accounts[0].name)
    assert len(ledger_actions) == 1
    assert len(trades) == 1

    report_config = list(buchfink_db.get_all_reports())[0]
    result = run_report(buchfink_db, accounts, report_config)

    assert float(result['overview']['trade']['taxable']) == pytest.approx(2092.35, rel=0.1)


def test_ledger_actions_airdrop(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_airdrop']

    _fetch(buchfink_db, accounts[0])

    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)

    assert len(trades) == 1

    report_config = list(buchfink_db.get_all_reports())[0]
    result = run_report(buchfink_db, accounts, report_config)

    assert float(result['overview']['trade']['taxable']) == pytest.approx(2092.35, rel=0.1)


def test_ledger_actions_gift(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_gift']

    _fetch(buchfink_db, accounts[0])

    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)
    ledger_actions = buchfink_db.get_local_ledger_actions_for_account(accounts[0].name)
    assert len(ledger_actions) == 1
    assert len(trades) == 1

    report_config = list(buchfink_db.get_all_reports())[0]
    result = run_report(buchfink_db, accounts, report_config)

    assert float(result['overview']['trade']['taxable']) == pytest.approx(2092.35, rel=0.1)


def test_ledger_actions_event_swap(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    accounts = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_event_swap']

    _fetch(buchfink_db, accounts[0])

    trades = buchfink_db.get_local_trades_for_account(accounts[0].name)
    ledger_actions = buchfink_db.get_local_ledger_actions_for_account(accounts[0].name)
    assert len(ledger_actions) == 4
    assert len(trades) == 0

    report_config = list(buchfink_db.get_all_reports())[1]
    result = run_report(buchfink_db, accounts, report_config)

    assert float(result['overview']['transaction event']['taxable']) == pytest.approx(100, rel=0.1)


def test_ledger_actions_mixed_swap_trade(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    account = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_mixed_swap_trade'][
        0
    ]
    _fetch(buchfink_db, account)
    trades = buchfink_db.get_local_trades_for_account(account.name)
    ledger_actions = buchfink_db.get_local_ledger_actions_for_account(account.name)
    assert len(ledger_actions) == 2
    assert len(trades) == 1

    report_config = list(buchfink_db.get_all_reports())[1]
    result = run_report(buchfink_db, [account], report_config)

    assert float(result['overview']['trade']['taxable']) == pytest.approx(100, rel=0.1)
    assert float(result['overview']['transaction event']['taxable']) == pytest.approx(0, rel=0.1)


def test_ledger_actions_mixed_same_link(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    account = [acc for acc in buchfink_db.get_all_accounts() if acc.name == 'acc_mixed_same_link'][
        0
    ]
    _fetch(buchfink_db, account)
    trades = buchfink_db.get_local_trades_for_account(account.name)
    ledger_actions = buchfink_db.get_local_ledger_actions_for_account(account.name)
    assert len(ledger_actions) == 2
    assert len(trades) == 2

    report_config = list(buchfink_db.get_all_reports())[1]
    with pytest.raises(ValueError, match=r'.*0x5.*'):
        run_report(buchfink_db, [account], report_config)
