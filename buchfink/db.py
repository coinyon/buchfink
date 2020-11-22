import logging
import os.path
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import click
import yaml
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.assets.resolver import AssetResolver
from rotkehlchen.chain.ethereum.eth2 import Eth2Deposit
from rotkehlchen.chain.ethereum.manager import EthereumManager
from rotkehlchen.chain.manager import BlockchainBalancesUpdate, ChainManager
from rotkehlchen.constants.assets import A_USD
from rotkehlchen.data.importer import DataImporter
from rotkehlchen.data_handler import DataHandler
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.settings import (DBSettings, ModifiableDBSettings,
                                     db_settings_from_dict)
from rotkehlchen.db.utils import BlockchainAccounts
from rotkehlchen.errors import (EthSyncError, InputError,
                                PremiumAuthenticationError, RemoteError,
                                SystemPermissionError)
from rotkehlchen.exchanges import ExchangeInterface
from rotkehlchen.exchanges.binance import Binance
from rotkehlchen.exchanges.bitmex import Bitmex
from rotkehlchen.exchanges.bittrex import Bittrex
from rotkehlchen.exchanges.coinbase import Coinbase
from rotkehlchen.exchanges.coinbasepro import Coinbasepro
from rotkehlchen.exchanges.gemini import Gemini
from rotkehlchen.exchanges.kraken import Kraken
from rotkehlchen.exchanges.manager import ExchangeManager
from rotkehlchen.exchanges.poloniex import Poloniex
from rotkehlchen.externalapis.coingecko import Coingecko
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.externalapis.etherscan import Etherscan
from rotkehlchen.fval import FVal
from rotkehlchen.greenlets import GreenletManager
from rotkehlchen.history import PriceHistorian, TradesHistorian
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.logging import (DEFAULT_ANONYMIZED_LOGS, LoggingSettings,
                                 RotkehlchenLogsAdapter)
from rotkehlchen.premium.premium import (Premium, PremiumCredentials,
                                         premium_create_and_verify)
from rotkehlchen.premium.sync import PremiumSyncManager
from rotkehlchen.typing import (ChecksumEthAddress, EthereumTransaction,
                                ExternalService, ExternalServiceApiCredentials,
                                Timestamp, TradeType)
from rotkehlchen.user_messages import MessagesAggregator

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.serialization import deserialize_trade

from .config import ReportConfig
from .schema import config_schema

try:
    # Bitcoinde module is not yet merged in Rotki, so we will make this optional
    from rotkehlchen.exchanges.bitcoinde import Bitcoinde
except ImportError:
    Bitcoinde = None
try:
    # Iconomi module is not yet merged in Rotki, so we will make this optional
    from rotkehlchen.exchanges.iconomi import Iconomi
except ImportError:
    Iconomi = None



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
        yaml_config = yaml.load(open(self.data_directory / 'buchfink.yaml', 'r'), Loader=yaml.SafeLoader)
        self.config = config_schema(yaml_config)

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
        self.coingecko = Coingecko()
        self.historian = PriceHistorian(self.cache_directory / 'history', '01/01/2014', self.cryptocompare)
        self.inquirer = Inquirer(self.cache_directory / 'inquirer', self.cryptocompare, self.coingecko)
        self.msg_aggregator = MessagesAggregator()
        self.greenlet_manager = GreenletManager(msg_aggregator=self.msg_aggregator)

        # Initialize blockchain querying modules
        self.etherscan = Etherscan(database=self, msg_aggregator=self.msg_aggregator)
        self.all_eth_tokens = AssetResolver().get_all_eth_token_info()
        self.ethereum_manager = EthereumManager(
            database=self,
            ethrpc_endpoint=self.get_eth_rpc_endpoint(),
            etherscan=self.etherscan,
            msg_aggregator=self.msg_aggregator,
            greenlet_manager=self.greenlet_manager,
            connect_at_start=[]
        )
        self.inquirer.inject_ethereum(self.ethereum_manager)
        #self.chain_manager = ChainManager(
        #    blockchain_accounts=[],
        #    owned_eth_tokens=[],
        #    ethereum_manager=self.ethereum_manager,
        #    msg_aggregator=self.msg_aggregator,
        #    greenlet_manager=self.greenlet_manager,
        #    premium=False,
        #    eth_modules=ethereum_modules,
        #)
        #self.ethereum_analyzer = EthereumAnalyzer(
        #    ethereum_manager=self.ethereum_manager,
        #    database=self,
        #)
        #self.trades_historian = TradesHistorian(
        #    user_directory=self.cache_directory,
        #    db=self,
        #    msg_aggregator=self.msg_aggregator,
        #    exchange_manager=None,
        #    chain_manager=self.chain_manager,
        #)

    def __del__(self):
        pass

    def get_main_currency(self):
        return self.get_settings().main_currency

    def get_eth_rpc_endpoint(self):
        return self.config['settings'].get('eth_rpc_endpoint', None)

    def get_all_accounts(self) -> List[Any]:
        return self.config['accounts']

    def get_all_reports(self) -> Iterable[ReportConfig]:
        for report_info in self.config['reports']:
            yield ReportConfig(
                name=str(report_info['name']),
                title=report_info.get('title'),
                template=report_info.get('template'),
                from_dt=datetime.fromisoformat(str(report_info['from'])),
                to_dt=datetime.fromisoformat(str(report_info['to']))
            )

    def get_settings(self):
        clean_settings = dict(self.config['settings'])
        if 'external_services' in clean_settings:
            del clean_settings['external_services']
        return db_settings_from_dict(clean_settings, self.msg_aggregator)

    def get_ignored_assets(self):
        return []

    @property
    def last_write_ts(self):
        return 0

    def get_external_service_credentials(
            self,
            service_name: ExternalService,
    ) -> Optional[ExternalServiceApiCredentials]:
        """If existing it returns the external service credentials for the given service"""
        short_name = service_name.name.lower()
        api_key = self.config['settings'].get('external_services', {}).get(short_name)
        if not api_key:
            return None
        return ExternalServiceApiCredentials(service=service_name, api_key=api_key)

    def get_accountant(self) -> Accountant:
        return Accountant(self, None, self.msg_aggregator, True)

    def get_blockchain_accounts(self) -> BlockchainAccounts:
        return BlockchainAccounts(eth=[], btc=[])

    def get_local_trades_for_account(self, account: str) -> List[Trade]:

        account_info = [a for a in self.config['accounts'] if a['name'] == account][0]

        if 'exchange' in account_info:
            trades_file = os.path.join(self.data_directory, 'trades', account_info['name'] + '.yaml')
            exchange = yaml.load(open(trades_file, 'r'), Loader=yaml.SafeLoader)
            return [deserialize_trade(trade) for trade in exchange['trades']]

        elif 'file' in account_info:
            trades_file = os.path.join(self.data_directory, account_info['file'])
            exchange = yaml.load(open(trades_file, 'r'), Loader=yaml.SafeLoader)
            return [deserialize_trade(trade) for trade in exchange.get('trades', [])]

        elif 'ethereum' in account_info or 'bitcoin' in account_info:
            # Currently buchfink is not able to fetch trades for blockchain accounts
            return []

        else:
            raise ValueError('Invalid account: ' + account)

    def get_chain_manager(self, account: Any) -> ChainManager:
        if 'ethereum' in account:
            accounts = BlockchainAccounts(eth=[account['ethereum']], btc=[])
        elif 'bitcoin' in account:
            accounts = BlockchainAccounts(eth=[], btc=[account['bitcoin']])
        else:
            raise ValueError('Invalid account')

        return ChainManager(
            database=self,
            blockchain_accounts=accounts,
            data_directory=self.data_directory,
            ethereum_manager=self.ethereum_manager,
            msg_aggregator=self.msg_aggregator,
            greenlet_manager=self.greenlet_manager,
            premium=False,
            eth_modules=self.get_settings().active_modules
        )

    def get_eth2_deposits(
            self,
            from_ts: Optional[Timestamp] = None,
            to_ts: Optional[Timestamp] = None,
            address: Optional[ChecksumEthAddress] = None,
    ) -> List[Eth2Deposit]:
        return []

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

    def get_tokens_for_address_if_time(self, address, current_time):
        return None

    def save_tokens_for_address(self, address, tokens):
        pass

    def update_used_query_range(self, name: str, start_ts: Timestamp, end_ts: Timestamp) -> None:
        pass

    def update_used_block_query_range(self, name: str, from_block: int, to_block: int) -> None:
        pass

    def get_used_query_range(self, name: str) -> Optional[Tuple[Timestamp, Timestamp]]:
        return None

    def add_ethereum_transactions(
            self,
            ethereum_transactions: List[EthereumTransaction],
            from_etherscan: bool,
    ) -> None:
        pass

    def get_ethereum_transactions(
            self,
            from_ts: Optional[Timestamp] = None,
            to_ts: Optional[Timestamp] = None,
            address: Optional[ChecksumEthAddress] = None,
    ) -> List[EthereumTransaction]:
        return []
