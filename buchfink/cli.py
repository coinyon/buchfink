import logging
from datetime import date, datetime

import click
import yaml

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.db import BuchfinkDB
from buchfink.serialization import deserialize_trade, serialize_trades
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.settings import db_settings_from_dict
from rotkehlchen.exchanges.binance import Binance
from rotkehlchen.exchanges.coinbase import Coinbase
from rotkehlchen.exchanges.kraken import Kraken
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.history import PriceHistorian
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.user_messages import MessagesAggregator

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

logger = logging.getLogger(__name__)

epoch_start_ts = datetime(2015, 1, 1).timestamp()
epoch_end_ts = datetime(2021, 1, 1).timestamp()


@click.group()
def buchfink():
    pass


@buchfink.command()
def init():
    pass


@buchfink.command()
@click.option('--keyword', '-k', type=str, default=None)
def fetch(keyword):
    msg_aggregator = MessagesAggregator()
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
                    msg_aggregator
                )
        elif account['exchange'] == 'binance':
            exchange = Binance(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    msg_aggregator
                )
        elif account['exchange'] == 'coinbase':
            exchange = Coinbase(
                    str(account['api_key']),
                    str(account['secret']).encode(),
                    buchfink_db,
                    msg_aggregator
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
@click.option('--from', '-f', 'from_', type=str, required=True)
@click.option('--to', '-t', type=str, required=True)
def report(from_, to):
    "Run an ad-hoc report on your data"

    start_ts = datetime.fromisoformat(from_).timestamp()
    end_ts = datetime.fromisoformat(to).timestamp()

    buchfink_db = BuchfinkDB()

    all_trades = []

    for account in buchfink_db.get_all_accounts():
        all_trades.extend(buchfink_db.get_local_trades_for_account(account))

    click.echo("Collected {0} trades from {1} exchange account(s)"
            .format(len(all_trades), len(buchfink_db.get_all_accounts())))

    accountant = buchfink_db.get_accountant()
    overview = accountant.process_history(start_ts, end_ts, all_trades, [], [], [])

    print(overview)


if __name__ == '__main__':
    buchfink()
