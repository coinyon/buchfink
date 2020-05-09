import logging
import os.path
from datetime import date, datetime
from pathlib import Path
from typing import List

import click
import yaml

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.serialization import deserialize_trade
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.settings import db_settings_from_dict
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.history import PriceHistorian
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.typing import TradeType
from rotkehlchen.user_messages import MessagesAggregator


class BuchfinkDB(DBHandler):
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

    def get_all_accounts(self):
        return self.config['accounts']

    def get_settings(self):
        return db_settings_from_dict({}, None)

    def get_ignored_assets(self):
        return []

    def get_external_service_credentials(self, service_name: str):
        return None

    def get_accountant(self):
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
