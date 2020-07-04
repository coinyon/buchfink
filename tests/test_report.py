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

    result = run_report(buchfink_db, report)

    assert result['overview']['total_taxable_profit_loss'] == '15000'
