import logging
import sys
import operator
import os
import os.path
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

import yaml
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.assets.resolver import AssetResolver
from rotkehlchen.assets.types import AssetType
from rotkehlchen.chain.ethereum.manager import EthereumManager
from rotkehlchen.chain.ethereum.trades import AMMSwap
from rotkehlchen.chain.manager import ChainManager
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.settings import DBSettings, db_settings_from_dict
from rotkehlchen.db.utils import BlockchainAccounts
from rotkehlchen.errors import UnknownAsset
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
from rotkehlchen.externalapis.beaconchain import BeaconChain
from rotkehlchen.externalapis.coingecko import Coingecko
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.externalapis.etherscan import Etherscan
from rotkehlchen.globaldb import GlobalDBHandler
from rotkehlchen.globaldb.updates import AssetsUpdater
from rotkehlchen.greenlets import GreenletManager
from rotkehlchen.history.price import PriceHistorian
from rotkehlchen.history.types import HistoricalPrice, HistoricalPriceOracle
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.types import (ChecksumEthAddress, ExternalService,
                                ExternalServiceApiCredentials, FVal, Location,
                                Price, SupportedBlockchain, Timestamp)
from rotkehlchen.user_messages import MessagesAggregator

from buchfink.datatypes import (ActionType, Asset, Balance, BalanceSheet,
                                LedgerAction, Trade, NFT)
from buchfink.models import (Account, Config, ExchangeAccountConfig,
                             HistoricalPriceConfig, ManualAccountConfig,
                             ReportConfig)
from buchfink.models.account import accounts_from_config
from buchfink.serialization import (deserialize_asset, deserialize_balance,
                                    deserialize_ethereum_token,
                                    deserialize_ledger_action,
                                    deserialize_trade, serialize_balances)

logger = logging.getLogger(__name__)

PREMIUM_ONLY_ETH_MODULES = ['adex']


class BuchfinkDB(DBHandler):
    """
    This class is not very thought out and might need a refactor. Currently it
    does three things, namely:
    1) preparing classes from Rotki to be used by higher-level functions
    2) function as a Rotki DBHandler and provide data to Rotki classes
    3) load and parse Buchfink config
    """

    def __init__(self, config_file='./buchfink.yaml'):
        self.config_file = Path(config_file)

        with open(self.config_file, 'r') as cfg:
            yaml_config = yaml.load(cfg, Loader=yaml.SafeLoader)

        self.data_directory = self.config_file.parent
        self.config = Config(**yaml_config)
        self.accounts = accounts_from_config(self.config)  # type: List[Account]
        self._active_eth_address = None  # type: Optional[ChecksumEthAddress]

        self.reports_directory = self.data_directory / "reports"
        self.trades_directory = self.data_directory / "trades"
        self.cache_directory = self.data_directory / "cache"
        self.actions_directory = self.data_directory / "actions"
        self.balances_directory = self.data_directory / "balances"
        self.annotations_directory = self.data_directory / "annotations"
        self.user_data_dir = self.data_directory / "user"

        self.reports_directory.mkdir(exist_ok=True)
        self.trades_directory.mkdir(exist_ok=True)
        self.balances_directory.mkdir(exist_ok=True)
        self.cache_directory.mkdir(exist_ok=True)
        self.actions_directory.mkdir(exist_ok=True)
        self.user_data_dir.mkdir(exist_ok=True)
        (self.cache_directory / 'cryptocompare').mkdir(exist_ok=True)
        (self.cache_directory / 'history').mkdir(exist_ok=True)
        (self.cache_directory / 'inquirer').mkdir(exist_ok=True)
        (self.cache_directory / 'coingecko').mkdir(exist_ok=True)

        self.last_write_ts: Optional[Timestamp] = None

        self._amm_swaps = []  # type: List[AMMSwap]
        self.cryptocompare = Cryptocompare(self.cache_directory / 'cryptocompare', self)
        self.coingecko = Coingecko()
        self.historian = PriceHistorian(
                self.cache_directory / 'history',
                self.cryptocompare,
                self.coingecko
            )
        self.inquirer = Inquirer(self.cache_directory / 'inquirer',
                self.cryptocompare,
                self.coingecko
            )
        self.msg_aggregator = MessagesAggregator()
        self.greenlet_manager = GreenletManager(msg_aggregator=self.msg_aggregator)

        # Initialize blockchain querying modules
        self.etherscan = Etherscan(database=self, msg_aggregator=self.msg_aggregator)
        GlobalDBHandler._GlobalDBHandler__instance = None
        self.globaldb = GlobalDBHandler(self.cache_directory)
        self.asset_resolver = AssetResolver()
        self.assets_updater = AssetsUpdater(self.msg_aggregator)

        self.ethereum_manager = EthereumManager(
            ethrpc_endpoint=self.get_eth_rpc_endpoint(),
            etherscan=self.etherscan,
            msg_aggregator=self.msg_aggregator,
            greenlet_manager=self.greenlet_manager,
            connect_at_start=[]
        )
        self.inquirer.inject_ethereum(self.ethereum_manager)
        self.inquirer.set_oracles_order(self.get_settings().current_price_oracles)
        self.historian.set_oracles_order(self.get_settings().historical_price_oracles)
        self.beaconchain = BeaconChain(database=self, msg_aggregator=self.msg_aggregator)

        super().__init__(self.user_data_dir, 'password', self.msg_aggregator, None)

    def __del__(self) -> None:
        try:
            super().__del__()
        except NameError:
            # This weird construction is present because rotki used "open" in
            # the __del__ method, while Python is shutting down and "open" is
            # no longer available. So, ignore any NameError IF Python is shutting
            # down (sys.meta_path is None)
            if sys.meta_path is not None:
                raise

    def get_asset_by_symbol(self, symbol: str) -> Asset:
        # TODO: this indirection function could incorporate a custom mapping from yaml config
        return deserialize_asset(symbol)

    def get_main_currency(self):
        return self.get_settings().main_currency

    def get_eth_rpc_endpoint(self) -> str:
        return self.config.settings.eth_rpc_endpoint or ''

    def get_all_accounts(self) -> List[Account]:
        return self.accounts

    def get_all_reports(self) -> Iterable[ReportConfig]:
        for report in self.config.reports:
            yield ReportConfig(
                name=str(report.name),
                title=report.title,
                template=report.template,
                from_dt=datetime.fromisoformat(str(report.from_)),
                to_dt=datetime.fromisoformat(str(report.to))
            )

    def get_settings(self, have_premium: bool = False) -> DBSettings:
        clean_settings = self.config.settings.dict()
        if 'external_services' in clean_settings:
            del clean_settings['external_services']

        # Remove None values
        for k in list(clean_settings):
            if clean_settings[k] is None:
                del clean_settings[k]

        return db_settings_from_dict(clean_settings, self.msg_aggregator)

    def get_ignored_assets(self):
        return []

    def get_external_service_credentials(
            self,
            service_name: ExternalService,
    ) -> Optional[ExternalServiceApiCredentials]:
        """If existing it returns the external service credentials for the given service"""
        short_name = service_name.name.lower()
        if not self.config.settings.external_services:
            return None

        api_key = self.config.settings.external_services.dict()[short_name]
        if not api_key:
            return None

        return ExternalServiceApiCredentials(service=service_name, api_key=api_key)

    def get_accountant(self) -> Accountant:
        return Accountant(self, None, self.msg_aggregator, True, premium=None)

    def get_blockchain_accounts(self) -> BlockchainAccounts:
        accs = dict(eth=[], btc=[], ksm=[], dot=[], avax=[])  # type: dict
        if self._active_eth_address:
            accs['eth'].append(self._active_eth_address)
        return BlockchainAccounts(**accs)

    def get_trades_from_file(self, trades_file) -> List[Trade]:
        def safe_deserialize_trade(trade):
            try:
                return deserialize_trade(trade)
            except UnknownAsset:
                logger.warning('Ignoring trade with unknown asset: %s', trade)
                return None

        with open(trades_file, 'r') as trades_f:
            exchange = yaml.load(trades_f, Loader=yaml.SafeLoader)

        return [ser_trade
                for ser_trade in [
                    safe_deserialize_trade(trade) for trade in exchange.get('trades', [])]
                if ser_trade is not None] \
                + [ser_trade
                for ser_trade in [
                    safe_deserialize_trade(trade) for trade in exchange.get('actions', [])
                    if 'buy' in trade or 'sell' in trade]
                if ser_trade is not None]

    def get_local_trades_for_account(self, account_name: Union[str, Account]) -> List[Trade]:
        if isinstance(account_name, str):
            account = [a for a in self.accounts if a.name == account_name][0]  # type: Account
        else:
            account = account_name

        if account.account_type == 'file':
            if not isinstance(account.config, ManualAccountConfig):
                # TODO: this check should already be enforced by type system
                raise ValueError("Invalid account config")

            trades_file = os.path.join(self.data_directory, account.config.file)
            return self.get_trades_from_file(trades_file)

        trades_file = os.path.join(self.data_directory, 'trades', account.name + '.yaml')

        if os.path.exists(trades_file):
            return self.get_trades_from_file(trades_file)

        return []

    def get_actions_from_file(self, actions_file) -> List[LedgerAction]:
        def safe_deserialize_ledger_action(action):
            if 'buy' in action or 'sell' in action:
                return None
            try:
                return deserialize_ledger_action(action)
            except UnknownAsset:
                logger.warning('Ignoring ledger action with unknown asset: %s', action)
                return None

        with open(actions_file, 'r') as actions_f:
            exchange = yaml.load(actions_f, Loader=yaml.SafeLoader)

        return [ser_action
                for ser_action in [
                    safe_deserialize_ledger_action(action)
                    for action in exchange.get('actions', [])
                ]
                if ser_action is not None]

    def get_local_ledger_actions_for_account(self, account_name: Union[str, Account]) \
            -> List[LedgerAction]:
        if isinstance(account_name, str):
            account = [a for a in self.accounts if a.name == account_name][0]  # type: Account
        else:
            account = account_name

        if account.account_type == 'file':
            if not isinstance(account.config, ManualAccountConfig):
                # TODO: this check should already be enforced by type system
                raise ValueError("Invalid account config")

            actions_file = self.data_directory / account.config.file
            if actions_file.exists():
                return self.get_actions_from_file(actions_file)

        else:
            actions_file = self.data_directory / f'actions/{account.name}.yaml'
            if actions_file.exists():
                return self.get_actions_from_file(actions_file)

        return []

    def get_chain_manager(self, account: Account) -> ChainManager:
        if account.account_type == "ethereum":
            accounts = BlockchainAccounts(eth=[account.address], btc=[], ksm=[], dot=[], avax=[])
        elif account.account_type == "bitcoin":
            accounts = BlockchainAccounts(eth=[], btc=[account.address], ksm=[], dot=[], avax=[])
        else:
            raise ValueError('Unable to create chain manager for account')

        # Eventually we should allow premium credentials in config file
        premium = False

        eth_modules = self.get_settings().active_modules
        if not premium:
            eth_modules = [mod for mod in eth_modules if mod not in PREMIUM_ONLY_ETH_MODULES]

        logger.debug('Creating ChainManager with modules: %s', eth_modules)

        manager = ChainManager(
            database=self,
            blockchain_accounts=accounts,
            beaconchain=self.beaconchain,
            data_directory=self.data_directory,
            ethereum_manager=self.ethereum_manager,
            polkadot_manager=None,
            avalanche_manager=None,
            kusama_manager=None,
            msg_aggregator=self.msg_aggregator,
            btc_derivation_gap_limit=self.get_settings().btc_derivation_gap_limit,
            greenlet_manager=self.greenlet_manager,
            premium=premium,
            eth_modules=eth_modules
        )
        # Monkey-patch function that uses singleton
        manager.queried_addresses_for_module = lambda self, module = None: [account.address]
        return manager

    def get_exchange(self, account: str) -> ExchangeInterface:

        account_ = [a for a in self.accounts if a.name == account][0]
        account_config = account_.config

        if not isinstance(account_config, ExchangeAccountConfig):
            raise ValueError("Not an exchange account: " + account)

        exchange_opts = dict(
            name=account_config.name,
            api_key=str(account_config.api_key),
            secret=str(account_config.secret).encode(),
            database=self,
            msg_aggregator=self.msg_aggregator
        )

        if account_config.exchange == 'kraken':
            exchange = Kraken(**exchange_opts)
        elif account_config.exchange == 'binance':
            exchange = Binance(**exchange_opts)
        elif account_config.exchange == 'coinbase':
            exchange = Coinbase(**exchange_opts)
        elif account_config.exchange == 'coinbasepro':
            exchange = Coinbasepro(**exchange_opts, passphrase=str(account_config.passphrase))
        elif account_config.exchange == 'gemini':
            exchange = Gemini(**exchange_opts)
        elif account_config.exchange == 'bitmex':
            exchange = Bitmex(**exchange_opts)
        elif account_config.exchange == 'bittrex':
            exchange = Bittrex(**exchange_opts)
        elif account_config.exchange == 'poloniex':
            exchange = Poloniex(**exchange_opts)
        elif account_config.exchange == 'bitcoinde':
            exchange = Bitcoinde(**exchange_opts)
        elif account_config.exchange == 'iconomi':
            exchange = Iconomi(**exchange_opts)
        else:
            raise ValueError("Unknown exchange: " + account_config.exchange)

        return exchange

    def get_tokens_for_address_if_time(self, address, current_time):
        return None

    def save_tokens_for_address(self, address, tokens):
        pass

    def query_balances(self, account) -> BalanceSheet:
        if account.account_type == "exchange":
            exchange = self.get_exchange(account.name)

            api_key_is_valid, error = exchange.validate_api_key()

            if not api_key_is_valid:
                raise RuntimeError(error)

            balances, error = exchange.query_balances()

            if not error:
                logger.info(
                        'Fetched balances for %d assets from %s',
                        len(balances.keys()),
                        account.name
                    )
                return BalanceSheet(assets=balances, liabilities={})

            raise RuntimeError(error)

        if account.account_type == "ethereum":
            manager = self.get_chain_manager(account)

            # This is a little hack because query_balances sometimes hooks back
            # into out get_blockchain_accounts() without providing context (for
            # example from makerdao module).
            self._active_eth_address = account.address
            manager.query_balances(
                blockchain=SupportedBlockchain.ETHEREUM,
                force_token_detection=True
            )
            self._active_eth_address = None

            return reduce(operator.add, manager.balances.eth.values())

        if account.account_type == "bitcoin":
            manager = self.get_chain_manager(account)
            manager.query_balances()
            btc = Asset('BTC')

            return BalanceSheet(assets={
                btc: reduce(operator.add, manager.balances.btc.values())
            }, liabilities={})

        if account.account_type == "file":
            return self.get_balances_from_file(account.config.file)

        return BalanceSheet(assets={}, liabilities={})

    def query_nfts(self, account) -> List[NFT]:
        if account.account_type == "ethereum":
            manager = self.get_chain_manager(account)
            nfts = manager.get_module('nfts')
            nft_result = nfts.get_all_info(addresses=[account.address], ignore_cache=True)
            if account.address in nft_result.addresses:
                return nft_result.addresses[account.address]
        return []

    def fetch_balances(self, account):
        query_sheet = self.query_balances(account)
        logger.debug('Balances for %s before annotations: %s', account.name, query_sheet)
        path = self.annotations_directory / (account.name + '.yaml')
        if path.exists():
            query_sheet += self.get_balances_from_file(path)
        self.write_balances(account, query_sheet)

    def get_balances(self, account) -> BalanceSheet:
        path = self.balances_directory / (account.name + '.yaml')
        if path.exists():
            return self.get_balances_from_file(path)
        return BalanceSheet(assets={}, liabilities={})

    def get_balances_from_file(self, path) -> BalanceSheet:

        with open(path, 'r') as account_f:
            account = yaml.load(account_f, Loader=yaml.SafeLoader)

        assets = {}  # type: Dict[Asset, Balance]
        liabilities = {}  # type: Dict[Asset, Balance]

        if 'balances' in account:
            logger.warning('Found deprecated key "balances", please use "assets" instead.')
            for balance in account['balances']:
                balance, asset = deserialize_balance(balance, self)
                if asset in assets:
                    assets[asset] += balance
                else:
                    assets[asset] = balance

        if 'assets' in account:
            for balance in account['assets']:
                balance, asset = deserialize_balance(balance, self)
                if asset in assets:
                    assets[asset] += balance
                else:
                    assets[asset] = balance

        if 'liabilities' in account:
            for balance in account['liabilities']:
                balance, asset = deserialize_balance(balance, self)
                if asset in liabilities:
                    liabilities[asset] += balance
                else:
                    liabilities[asset] = balance

        return BalanceSheet(assets=assets, liabilities=liabilities)

    def write_balances(self, account: Account, balances: BalanceSheet):
        path = self.balances_directory / (account.name + '.yaml')

        try:
            with path.open('r') as balances_file:
                contents = yaml.load(balances_file, Loader=yaml.SafeLoader)
                if contents is None:
                    contents = {}
        except FileNotFoundError:
            contents = {}

        with path.open('w') as balances_file:
            contents.update(serialize_balances(balances))
            yaml.dump(contents, stream=balances_file, sort_keys=True)

    def get_amm_swaps(
            self,
            from_ts: Optional[Timestamp] = None,
            to_ts: Optional[Timestamp] = None,
            location: Optional[Location] = None,
            address: Optional[ChecksumEthAddress] = None,
    ) -> List[AMMSwap]:
        return self._amm_swaps

    def add_amm_swaps(self, swaps: List[AMMSwap]) -> None:
        self._amm_swaps = []
        self._amm_swaps.extend(swaps)

    def update_used_query_range(self, name: str, start_ts: Timestamp, end_ts: Timestamp) -> None:
        pass

    def update_used_block_query_range(self, name: str, from_block: int, to_block: int) -> None:
        pass

    def get_used_query_range(self, name: str) -> Optional[Tuple[Timestamp, Timestamp]]:
        return None

    def get_ignored_action_ids(
            self,
            action_type: Optional[ActionType],
            ) -> Dict[ActionType, List[str]]:
        return {}

    def add_asset_identifiers(self, asset_identifiers: List[str]) -> None:
        pass

    def get_binance_pairs(self, name: str, location: Location) -> List[str]:
        return []

    def perform_assets_updates(self):
        self.assets_updater.perform_update(None, None)

        for token in self.config.tokens:
            eth_token = deserialize_ethereum_token(token.dict())
            identifier = '_ceth_' + eth_token.ethereum_address

            try:
                self.get_asset_by_symbol(identifier)
                logger.debug('Asset already exists: %s', eth_token)
            except UnknownAsset:
                self.globaldb.add_asset(identifier, AssetType.ETHEREUM_TOKEN, eth_token)
                try:
                    self.get_asset_by_symbol(identifier)
                except UnknownAsset as exc:
                    raise ValueError('Unable to add asset: ' + str(eth_token)) from exc

            self.asset_resolver.clean_memory_cache()

    def apply_manual_prices(self):
        def to_historical_price(historical_price: HistoricalPriceConfig) -> HistoricalPrice:
            return HistoricalPrice(
                from_asset=self.get_asset_by_symbol(historical_price.from_),
                to_asset=self.get_asset_by_symbol(historical_price.to),
                source=HistoricalPriceOracle.MANUAL,
                price=Price(FVal(str(historical_price.price))),
                timestamp=Timestamp(int(historical_price.at.timestamp()))
            )

        prices = [to_historical_price(historical_price) for historical_price in self.config.prices]
        for price in prices:
            logger.debug('Adding %s', price)
            self.globaldb.delete_historical_prices(
                    price.from_asset,
                    price.to_asset,
                    HistoricalPriceOracle.MANUAL
            )
        self.globaldb.add_historical_prices(prices)
