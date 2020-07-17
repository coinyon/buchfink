import datetime
import logging
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from buchfink.db import BuchfinkDB

from .config import ReportConfig

logger = logging.getLogger(__name__)


def run_report(buchfink_db: BuchfinkDB, report_config: ReportConfig):
    name = report_config.name
    start_ts = report_config.from_dt.timestamp()
    end_ts = report_config.to_dt.timestamp()
    num_matched_accounts = 0
    all_trades = []

    logger.info('Generating report "%s"...', name)

    for account in buchfink_db.get_all_accounts():
        num_matched_accounts += 1
        all_trades.extend(buchfink_db.get_local_trades_for_account(account['name']))

    logger.info('Collected %d trades from %d exchange account(s)',
            len(all_trades), num_matched_accounts)

    accountant = buchfink_db.get_accountant()
    result = accountant.process_history(start_ts, end_ts, all_trades, [], [], [], [])
    accountant.csvexporter.create_files(buchfink_db.reports_directory / Path(name))

    with (buchfink_db.reports_directory / Path(name) / 'report.yaml').open('w') as report_file:
        yaml.dump({ 'overview': result['overview'] }, stream=report_file)

    logger.info('Report information has been written to: %s',
            buchfink_db.reports_directory / Path(name)
    )

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

        # TODO: get ext from template path. could also be json, csv, ...
        ext = '.html'

        # to save the results
        with open(buchfink_db.reports_directory / Path(name) / ('report' + ext), "w") as fh:
            fh.write(rendered_report)

        logger.info("Rendered temmplate to 'report%s'.", ext)

    return result
