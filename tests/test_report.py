import os.path
import shutil

# import pytest

from buchfink.db import BuchfinkDB
from buchfink.report import run_report, render_report


def test_bullrun_config(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 2

    report = reports[0]

    assert report.name == 'all'
    assert report.from_dt.year == 2015
    assert report.to_dt.year == 2019

    result = run_report(buchfink_db, buchfink_db.get_all_accounts(), report)

    assert result['overview']['trade']['taxable'] == '15000'


def test_bullrun_report_template(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 2

    report = reports[1]

    assert report.name == 'withtemplate'
    assert report.from_dt.year == 2015
    assert report.to_dt.year == 2019

    result = run_report(buchfink_db, buchfink_db.get_all_accounts(), report)

    assert result['overview']['trade']['taxable'] == '15000'


def test_manual_price(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'ledger_actions'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    buchfink_db.sync_manual_prices()

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 2

    report = reports[1]

    assert report.name == '2020'
    assert report.from_dt.year == 2020
    assert report.to_dt.year == 2021

    acc = [a for a in buchfink_db.get_all_accounts() if a.name == 'acc_manual_price']

    result = run_report(buchfink_db, acc, report)

    # Even we made 30 USD, only 20 is taxable, because
    # price was 0.01 at buy (see acc_manual_price.yaml)
    # and 0.03 at sell (coingecko)
    assert float(result['overview']['trade']['taxable']) == 20.0


def test_ethereum_gas_report(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "scenarios", "ethereum_gas"),
        os.path.join(tmp_path, "buchfink"),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, "buchfink/buchfink.yaml"))
    buchfink_db.perform_assets_updates()

    reports = list(buchfink_db.get_all_reports())

    assert len(reports) == 1

    report = reports[0]

    assert report.name == 'all'

    whale1, whale2 = buchfink_db.get_all_accounts()

    result = run_report(buchfink_db, [whale1], report)

    assert float(result['overview']['trade']['taxable']) == 500.0
    # TODO
    # assert float(result['overview']['transaction event']['taxable']) == \
    #         pytest.approx(-64.816, rel=0.1)

    render_report(buchfink_db, report)

    report_file = os.path.join(tmp_path, "buchfink", "reports", report.name, "report.md")

    assert os.path.exists(report_file)

    with open(report_file, 'r') as report_handle:
        report_contents = report_handle.read()
        assert '## Events' in report_contents
        # TODO
        # assert '0.0203' in report_contents
        # assert '-64.81' in report_contents

    result = run_report(buchfink_db, [whale2], report)

    assert float(result['overview']['trade']['taxable']) == 500.0
    # TODO
    # assert float(result['overview']['transaction event']['taxable']) == \
    #       pytest.approx(-64.816, rel=0.01)

    render_report(buchfink_db, report)

    with open(report_file, 'r') as report_handle:
        report_contents = report_handle.read()
        assert '## Events' in report_contents
        # TODO
        # assert '0.0203' in report_contents
        # assert '-64.81' in report_contents
