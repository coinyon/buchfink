import os.path

from buchfink.db import BuchfinkDB
from buchfink.report import run_report


def test_bullrun_config():
    buchfink_db = BuchfinkDB(os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'))

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 1

    report = reports[0]

    assert report.name == 'all'
    assert report.from_dt.year == 2015
    assert report.to_dt.year == 2020

    result = run_report(buchfink_db, buchfink_db.get_all_accounts(), report)

    assert result['overview']['total_taxable_profit_loss'] == '15000'


def test_unknown_price():
    buchfink_db = BuchfinkDB(os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'))

    buchfink_db.apply_manual_prices()

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 1

    report = reports[0]

    assert report.name == 'all'
    assert report.from_dt.year == 2020
    assert report.to_dt.year == 2021

    acc = [a for a in buchfink_db.get_all_accounts() if a.name=='acc_unknown_price']

    result = run_report(buchfink_db, acc, report)

    # Even we made 30 USD, only 20 is taxable, because
    # price was 0.01 at buy (see acc_unknown_price.yaml)
    # and 0.03 at sell (coingecko)
    assert float(result['overview']['total_taxable_profit_loss']) == 20.0
