import os.path
from datetime import datetime

from buchfink.db import BuchfinkDB


def test_bullrun_full_taxes():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    config = os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config)

    trades = buchfink_db.get_local_trades_for_account('exchange1')

    assert len(trades) == 2

    accountant = buchfink_db.get_accountant()
    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], [])

    assert result['overview']['general_trade_profit_loss'] == '15000'
    assert result['overview']['taxable_trade_profit_loss'] == '15000'
    assert result['overview']['total_taxable_profit_loss'] == '15000'


def test_bullrun_no_taxes():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    config = os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config)

    trades = buchfink_db.get_local_trades_for_account('exchange2')

    assert len(trades) == 2

    accountant = buchfink_db.get_accountant()
    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], [])

    assert result['overview']['general_trade_profit_loss'] == '7000'
    assert result['overview']['taxable_trade_profit_loss'] == '0'
    assert result['overview']['total_taxable_profit_loss'] == '0'


def test_ledger_actions_income():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    config = os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config)
    accountant = buchfink_db.get_accountant()

    trades = buchfink_db.get_local_trades_for_account('acc_income')

    assert len(trades) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], [])

    assert result['overview']['general_trade_profit_loss'] == '3000'
    assert result['overview']['taxable_trade_profit_loss'] == '3000'
    assert result['overview']['total_taxable_profit_loss'] == '3000'

    ledger_actions = buchfink_db.get_local_ledger_actions_for_account('acc_income')
    assert len(ledger_actions) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], ledger_actions)

    assert result['overview']['general_trade_profit_loss'] == '2092.35'
    assert result['overview']['taxable_trade_profit_loss'] == '2092.35'
    assert result['overview']['total_taxable_profit_loss'] == '3000.00'


def test_ledger_actions_airdrop():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    config = os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config)
    accountant = buchfink_db.get_accountant()

    trades = buchfink_db.get_local_trades_for_account('acc_airdrop')

    assert len(trades) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], [])

    assert result['overview']['general_trade_profit_loss'] == '3000'
    assert result['overview']['taxable_trade_profit_loss'] == '3000'
    assert result['overview']['total_taxable_profit_loss'] == '3000'

    ledger_actions = buchfink_db.get_local_ledger_actions_for_account('acc_airdrop')
    assert len(ledger_actions) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], ledger_actions)

    assert result['overview']['general_trade_profit_loss'] == '2092.35'
    assert result['overview']['taxable_trade_profit_loss'] == '2092.35'
    assert result['overview']['total_taxable_profit_loss'] == '2092.35'


def test_ledger_actions_gift():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    config = os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions', 'buchfink.yaml')
    buchfink_db = BuchfinkDB(config)
    accountant = buchfink_db.get_accountant()

    trades = buchfink_db.get_local_trades_for_account('acc_gift')

    assert len(trades) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], [])

    assert result['overview']['general_trade_profit_loss'] == '3000'
    assert result['overview']['taxable_trade_profit_loss'] == '3000'
    assert result['overview']['total_taxable_profit_loss'] == '3000'

    ledger_actions = buchfink_db.get_local_ledger_actions_for_account('acc_gift')
    assert len(ledger_actions) == 1

    result = accountant.process_history(start_ts, end_ts, trades, [], [], [], [], ledger_actions)

    assert result['overview']['general_trade_profit_loss'] == '2092.35'
    assert result['overview']['taxable_trade_profit_loss'] == '2092.35'
    assert result['overview']['total_taxable_profit_loss'] == '2092.35'
