import datetime
import logging
from pathlib import Path
from typing import List

import yaml
from jinja2 import Environment, FileSystemLoader

from buchfink.db import BuchfinkDB

from .models import Account, ReportConfig

logger = logging.getLogger(__name__)


def run_report(buchfink_db: BuchfinkDB, accounts: List[Account], report_config: ReportConfig):
    name = report_config.name
    start_ts = report_config.from_dt.timestamp()
    end_ts = report_config.to_dt.timestamp()
    num_matched_accounts = 0
    all_trades = []
    all_actions = []

    root_logger = logging.getLogger('')
    formatter = logging.Formatter('%(levelname)s: %(message)s')

    folder = buchfink_db.reports_directory / Path(name)
    folder.mkdir(exist_ok=True)

    logfile = folder / 'report.log'
    if logfile.exists():
        logfile.unlink()
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logfile = folder / 'errors.log'
    if logfile.exists():
        logfile.unlink()
    error_handler = logging.FileHandler(logfile)
    error_handler.setLevel(logging.DEBUG)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    logger.info('Generating report "%s"...', name)

    for account in accounts:
        num_matched_accounts += 1
        all_trades.extend(buchfink_db.get_local_trades_for_account(account))
        all_actions.extend(buchfink_db.get_local_ledger_actions_for_account(account))

    logger.info('Collected %d trades / %d actions from %d exchange account(s)',
            len(all_trades), len(all_actions), num_matched_accounts)

    accountant = buchfink_db.get_accountant()
    result = accountant.process_history(start_ts, end_ts, all_trades, [], [], [], [], all_actions)
    accountant.csvexporter.create_files(buchfink_db.reports_directory / Path(name))

    with (folder / 'report.yaml').open('w') as report_file:
        yaml.dump({'overview': result['overview']}, stream=report_file)

    logger.info('Report information has been written to: %s',
            buchfink_db.reports_directory / Path(name)
    )

    root_logger.removeHandler(file_handler)
    root_logger.removeHandler(error_handler)

    if report_config.template:
        # Look for templates relative to the data_directory, that is the directory where
        # the buchfink.yaml is residing.
        env = Environment(loader=FileSystemLoader(buchfink_db.data_directory))
        env.globals['datetime'] = datetime
        env.globals['float'] = float
        env.globals['str'] = str
        template = env.get_template(report_config.template)
        rendered_report = template.render({
            "name": report_config.name,
            "title": report_config.title,
            "overview": result['overview'],
            "events": result['all_events']
        })

        # we should get ext from template path. could also be json, csv, ...
        ext = '.html'

        # to save the results
        with open(buchfink_db.reports_directory / Path(name) / ('report' + ext), "w") as reportf:
            reportf.write(rendered_report)

        logger.info("Rendered temmplate to 'report%s'.", ext)

    return result
