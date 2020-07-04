import logging
import os.path
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Any, Iterable

import click
import yaml

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.serialization import deserialize_trade
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.settings import db_settings_from_dict
from rotkehlchen.exchanges import ExchangeInterface
from rotkehlchen.exchanges.binance import Binance
from rotkehlchen.exchanges.bitcoinde import Bitcoinde
from rotkehlchen.exchanges.bitmex import Bitmex
from rotkehlchen.exchanges.bittrex import Bittrex
from rotkehlchen.exchanges.coinbase import Coinbase
from rotkehlchen.exchanges.coinbasepro import Coinbasepro
from rotkehlchen.exchanges.gemini import Gemini
from rotkehlchen.exchanges.iconomi import Iconomi
from rotkehlchen.exchanges.kraken import Kraken
from rotkehlchen.exchanges.poloniex import Poloniex
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.history import PriceHistorian
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.typing import TradeType
from rotkehlchen.user_messages import MessagesAggregator

from .config import ReportConfig


class BuchfinkDB(DBHandler):
    """
    This class is not very thought out and might need a refactor. Currently it
    does three things, namely:
    1) preparing classes from Rotki to be used by higher-level functions
    2) function as a Rotki DBHandler and provide data to Rotki classes
    3) load and parse Buchfink config
    """

    def __init__(self, data_directory='.'):
        self.data_directory = Path(data_directory)
        self.config = yaml.load(open(self.data_directory / 'buchfink.yaml', 'r'), Loader=yaml.SafeLoader)

        self.reports_directory = self.data_directory / "reports"
        self.trades_directory = self.data_directory / "trades"
        self.cache_directory = self.data_directory / "cache"

        self.reports_directory.mkdir(exist_ok=True)
        self.trades_directory.mkdir(exist_ok=True)
        self.cache_directory.mkdir(exist_ok=True)
        (self.cache_directory / 'cryptocompare').mkdir(exist_ok=True)
        (self.cache_directory / 'history').mkdir(exist_ok=True)
        (self.cache_directory / 'inquirer').mkdir(exist_ok=True)

        self.cryptocompare = Cryptocompare(self.cache_directory / 'cryptocompare', self)
        self.historian = PriceHistorian(self.cache_directory / 'history', '01/01/2015', self.cryptocompare)
        self.inquirer = Inquirer(self.cache_directory / 'inquirer', self.cryptocompare)
        self.msg_aggregator = MessagesAggregator()

    def __del__(self):
        pass

    def get_main_currency(self):
        return Asset(self.config['settings']['main_currency'])

    def get_all_accounts(self) -> List[Any]:
        return self.config['accounts']

    def get_all_reports(self) -> Iterable[ReportConfig]:
        for report_info in self.config['reports']:
            yield ReportConfig(
                name=str(report_info['name']),
                from_dt=datetime.fromisoformat(str(report_info['from'])),
                to_dt=datetime.fromisoformat(str(report_info['to']))
            )

    def get_settings(self):
        return db_settings_from_dict({}, None)

    def get_ignored_assets(self):
        return []

    def get_external_service_credentials(self, service_name: str):
        return None

    def get_accountant(self) -> Accountant:
        return Accountant(self, None, self.msg_aggregator, True)

    def get_local_trades_for_account(self, account: str) -> List[Trade]:

        account_info = [a for a in self.config['accounts'] if a['name'] == account][0]

        if 'exchange' in account_info:
            trades_file = os.path.join(self.data_directory, 'trades', account_info['name'] + '.yaml')
            exchange = yaml.load(open(trades_file, 'r'), Loader=yaml.SafeLoader)
            return [deserialize_trade(trade) for trade in exchange['trades']]

        elif 'file' in account_info:
            trades_file = os.path.join(self.data_directory, account_info['file'])
            exchange = yaml.load(open(trades_file, 'r'), Loader=yaml.SafeLoader)
            return [deserialize_trade(trade) for trade in exchange['trades']]

        else:
            raise ValueError('Unable to parse account')

    def get_exchange(self, account: str) -> ExchangeInterface:

        account_info = [a for a in self.config['accounts'] if a['name'] == account][0]

        if account_info['exchange'] == 'kraken':
            exchange = Kraken(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'binance':
            exchange = Binance(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'coinbase':
            exchange = Coinbase(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'coinbasepro':
            exchange = Coinbasepro(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator,
                    str(account_info['passphrase'])
                )
        elif account_info['exchange'] == 'gemini':
            exchange = Gemini(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'bitmex':
            exchange = Bitmex(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'bittrex':
            exchange = Bittrex(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'poloniex':
            exchange = Poloniex(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'bitcoinde':
            exchange = Bitcoinde(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        elif account_info['exchange'] == 'iconomi':
            exchange = Iconomi(
                    str(account_info['api_key']),
                    str(account_info['secret']).encode(),
                    self,
                    self.msg_aggregator
                )
        else:
            raise ValueError("Unknown exchange: " + account_info['exchange'])

        return exchange
