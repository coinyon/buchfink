import logging
import os.path
import shutil
from datetime import date, datetime

import click
import coloredlogs
import yaml

from buchfink.db import BuchfinkDB
from buchfink.serialization import deserialize_trade, serialize_trades
from rotkehlchen.exchanges.binance import Binance
from rotkehlchen.exchanges.bitmex import Bitmex
from rotkehlchen.exchanges.bittrex import Bittrex
from rotkehlchen.exchanges.coinbase import Coinbase
from rotkehlchen.exchanges.coinbasepro import Coinbasepro
from rotkehlchen.exchanges.gemini import Gemini
from rotkehlchen.exchanges.kraken import Kraken
from rotkehlchen.exchanges.poloniex import Poloniex
from pathlib import Path

logger = logging.getLogger(__name__)

epoch_start_ts = datetime(2015, 1, 1).timestamp()
epoch_end_ts = datetime(2021, 1, 1).timestamp()


@click.group()
@click.option('--log-level', '-l', type=str, default='INFO')
def buchfink(log_level):
    coloredlogs.install(level=log_level, fmt='%(asctime)s %(name)s %(levelname)s %(message)s')


@buchfink.command()
@click.option('--directory', '-d', type=str, default='.')
def init(directory):
    target_config = os.path.join(directory, 'buchfink.yaml')

    if os.path.exists(target_config):
        click.echo(click.style('Already initialized (buchfink.yaml exists), aborting.', fg='red'))
        return

    initial_config = os.path.join(os.path.dirname(__file__), 'data', 'buchfink.initial.yaml')
    shutil.copyfile(initial_config, target_config)

    buchfink_db = BuchfinkDB(directory)

    click.echo(click.style('Successfully initialized in {0}.'.format(buchfink_db.data_directory.absolute()), fg='green'))


@buchfink.command()
@click.option('--keyword', '-k', type=str, default=None)
def fetch(keyword):
    buchfink_db = BuchfinkDB()

    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account['name']:
            continue

        if 'exchange' not in account:
            continue

        click.echo('Fetching trades for ' + account['name'])

        if account['exchange'] == 'kraken':
            exchange = Kraken(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'binance':
            exchange = Binance(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'coinbase':
            exchange = Coinbase(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'coinbasepro':
            exchange = Coinbasepro(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'gemini':
            exchange = Gemini(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'bitmex':
            exchange = Bitmex(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'bittrex':
            exchange = Bittrex(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        elif account['exchange'] == 'poloniex':
            exchange = Poloniex(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    buchfink_db.msg_aggregator
                )
        else:
            raise ValueError("Unknown exchange: " + account['exchange'])

        name = account.get('name')

        trades = exchange.query_online_trade_history(
            start_ts=epoch_start_ts,
            end_ts=epoch_end_ts
        )

        logger.info('Fetched %d trades from %s', len(trades), name)

        with open("trades/" + name + ".yaml", "w") as f:
            yaml.dump({"trades": serialize_trades(trades)}, stream=f)


@buchfink.command()
@click.option('--name', '-n', type=str, required=True)
@click.option('--from', '-f', 'from_', type=str, required=True)
@click.option('--to', '-t', type=str, required=True)
def report(name, from_, to):
    "Run an ad-hoc report on your data"

    start_ts = datetime.fromisoformat(from_).timestamp()
    end_ts = datetime.fromisoformat(to).timestamp()

    buchfink_db = BuchfinkDB()

    all_trades = []

    for account in buchfink_db.get_all_accounts():
        all_trades.extend(buchfink_db.get_local_trades_for_account(account['name']))

    logger.info('Generating report "%s"...', name)

    click.echo("Collected {0} trades from {1} exchange account(s)"
            .format(len(all_trades), len(buchfink_db.get_all_accounts())))

    accountant = buchfink_db.get_accountant()
    result = accountant.process_history(start_ts, end_ts, all_trades, [], [], [])
    accountant.csvexporter.create_files(buchfink_db.reports_directory / Path(name))

    logger.info("Overview: %s", result['overview'])


if __name__ == '__main__':
    buchfink()
