import logging
import operator
import os
import os.path
import sys
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple, Union, cast

import yaml
from rotkehlchen.accounting.accountant import Accountant
from rotkehlchen.assets.resolver import AssetResolver
from rotkehlchen.assets.spam_assets import update_spam_assets
from rotkehlchen.assets.types import AssetType
from rotkehlchen.assets.utils import get_or_create_evm_token
from rotkehlchen.chain.aggregator import ChainsAggregator
from rotkehlchen.chain.ethereum.accountant import EthereumAccountingAggregator
from rotkehlchen.chain.ethereum.decoding.decoder import EthereumTransactionDecoder
from rotkehlchen.chain.ethereum.etherscan import EthereumEtherscan
from rotkehlchen.chain.ethereum.manager import EthereumManager
from rotkehlchen.chain.ethereum.node_inquirer import EthereumInquirer
from rotkehlchen.chain.ethereum.oracles.saddle import SaddleOracle
from rotkehlchen.chain.ethereum.oracles.uniswap import UniswapV2Oracle, UniswapV3Oracle
from rotkehlchen.chain.ethereum.transactions import EthereumTransactions
from rotkehlchen.chain.evm.accounting.aggregator import EVMAccountingAggregators
from rotkehlchen.chain.evm.transactions import EvmTransactionsFilterQuery
from rotkehlchen.chain.evm.types import NodeName, WeightedNode
from rotkehlchen.constants.misc import DEFAULT_SQL_VM_INSTRUCTIONS_CB
from rotkehlchen.data_migrations.manager import DataMigrationManager
from rotkehlchen.data_migrations.migrations.migration_4 import read_and_write_nodes_in_database
from rotkehlchen.db.dbhandler import DBHandler
from rotkehlchen.db.evmtx import DBEvmTx
from rotkehlchen.db.settings import DBSettings, db_settings_from_dict
from rotkehlchen.exchanges.binance import Binance
from rotkehlchen.exchanges.bitcoinde import Bitcoinde
from rotkehlchen.exchanges.bitmex import Bitmex
from rotkehlchen.exchanges.bittrex import Bittrex
from rotkehlchen.exchanges.coinbase import Coinbase
from rotkehlchen.exchanges.coinbasepro import Coinbasepro
from rotkehlchen.exchanges.exchange import ExchangeInterface
from rotkehlchen.exchanges.gemini import Gemini
from rotkehlchen.exchanges.iconomi import Iconomi
from rotkehlchen.exchanges.kraken import Kraken
from rotkehlchen.exchanges.poloniex import Poloniex
from rotkehlchen.externalapis.beaconchain import BeaconChain
from rotkehlchen.externalapis.coingecko import Coingecko
from rotkehlchen.externalapis.cryptocompare import Cryptocompare
from rotkehlchen.externalapis.defillama import Defillama
from rotkehlchen.globaldb.handler import GlobalDBHandler
from rotkehlchen.globaldb.manual_price_oracles import ManualCurrentOracle
from rotkehlchen.globaldb.updates import AssetsUpdater
from rotkehlchen.greenlets.manager import GreenletManager
from rotkehlchen.history.price import PriceHistorian
from rotkehlchen.history.types import HistoricalPrice, HistoricalPriceOracle
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.logging import TRACE, add_logging_level
from rotkehlchen.types import (
    SPAM_PROTOCOL,
    ChainID,
    ChecksumEvmAddress,
    ExternalService,
    ExternalServiceApiCredentials,
    FVal,
    Location,
    Price,
    SupportedBlockchain,
    Timestamp
)
from rotkehlchen.user_messages import MessagesAggregator
from rotkehlchen.utils.misc import ts_now

from buchfink.datatypes import (
    ActionType,
    Asset,
    BalanceSheet,
    BlockchainAccountData,
    BlockchainAccounts,
    EvmAccount,
    EvmTransaction,
    EvmTxReceipt,
    HistoryBaseEntry,
    LedgerAction,
    Nfts,
    Trade
)
from buchfink.exceptions import InputError, UnknownAsset
from buchfink.models import (
    Account,
    Config,
    ExchangeAccountConfig,
    HistoricalPriceConfig,
    ManualAccountConfig,
    ReportConfig
)
from buchfink.models.account import accounts_from_config
from buchfink.serialization import (
    deserialize_asset,
    deserialize_balance,
    deserialize_event,
    deserialize_evm_token,
    deserialize_identifier,
    deserialize_ledger_action,
    deserialize_trade,
    serialize_balances
)

if TYPE_CHECKING:
    from .datatypes import Balance  # noqa: F401

logger = logging.getLogger(__name__)

PREMIUM_ONLY_ETH_MODULES = ['adex']
ENABLE_DATA_MIGRATION = False

if __debug__:
    add_logging_level('TRACE', TRACE)


class BuchfinkDB(DBHandler):
    """
    This class is not very thought out and might need a refactor. Currently it
    does three things, namely:
    1) preparing classes from Rotki to be used by higher-level functions
    2) function as a Rotki DBHandler and provide data to Rotki classes
    3) load and parse Buchfink config
    """

    def __init__(self, config_file: str = './buchfink.yaml'):
        self.config_file = Path(config_file)

        with open(self.config_file, 'r') as cfg:
            yaml_config = yaml.load(cfg, Loader=yaml.SafeLoader)

        self.data_directory = self.config_file.parent
        self.config = Config(**yaml_config)
        self.accounts = accounts_from_config(self.config)  # type: List[Account]
        self._active_eth_address = None  # type: Optional[ChecksumEvmAddress]

        # Buchfink directories, these include the YAML storage and the reports
        # etc. Basically these are the ones you want version-controlled.
        self.reports_directory = self.data_directory / "reports"
        self.trades_directory = self.data_directory / "trades"
        self.actions_directory = self.data_directory / "actions"
        self.balances_directory = self.data_directory / "balances"
        self.annotations_directory = self.data_directory / "annotations"
        self.reports_directory.mkdir(exist_ok=True)
        self.trades_directory.mkdir(exist_ok=True)
        self.actions_directory.mkdir(exist_ok=True)
        self.balances_directory.mkdir(exist_ok=True)
        self.annotations_directory.mkdir(exist_ok=True)

        # Rotki files, these are treated as a cache from Buchfinks perspective.
        # You should be able to delete them and have them automatically rebuild
        # by Buchfink. Ignore them in version control.
        self.cache_directory = self.data_directory / ".buchfink"
        self.user_data_dir = self.cache_directory / "user"
        self.cache_directory.mkdir(exist_ok=True)
        self.user_data_dir.mkdir(exist_ok=True)
        (self.cache_directory / 'cryptocompare').mkdir(exist_ok=True)
        (self.cache_directory / 'history').mkdir(exist_ok=True)
        (self.cache_directory / 'inquirer').mkdir(exist_ok=True)
        (self.cache_directory / 'coingecko').mkdir(exist_ok=True)

        self.last_write_ts: Optional[Timestamp] = None

        # self._amm_swaps = []  # type: List[AMMSwap]
        self.msg_aggregator = MessagesAggregator()
        self.cryptocompare = Cryptocompare(self.cache_directory / 'cryptocompare', self)
        self.coingecko = Coingecko()
        self.defillama = Defillama()
        self.historian = PriceHistorian(
                self.cache_directory / 'history',
                self.cryptocompare,
                self.coingecko,
                self.defillama
            )

        self.greenlet_manager = GreenletManager(msg_aggregator=self.msg_aggregator)

        # Initialize blockchain querying modules
        self.etherscan = EthereumEtherscan(database=self, msg_aggregator=self.msg_aggregator)
        GlobalDBHandler._GlobalDBHandler__instance = None
        self.globaldb = GlobalDBHandler(
            data_dir=self.cache_directory,
            sql_vm_instructions_cb=DEFAULT_SQL_VM_INSTRUCTIONS_CB
        )
        self.asset_resolver = AssetResolver()
        self.assets_updater = AssetsUpdater(self.msg_aggregator)

        self.inquirer = Inquirer(
                data_dir=self.cache_directory / 'inquirer',
                cryptocompare=self.cryptocompare,
                coingecko=self.coingecko,
                manualcurrent=ManualCurrentOracle(),
                msg_aggregator=self.msg_aggregator,
                defillama=self.defillama
            )

        # After calling the parent constructor, we will have a db connection.
        super().__init__(
                self.user_data_dir,
                'password',
                self.msg_aggregator,
                None,
                sql_vm_instructions_cb=DEFAULT_SQL_VM_INSTRUCTIONS_CB
        )

        if ENABLE_DATA_MIGRATION:
            class FakeRotki():
                class FakeData():
                    db = self
                data = FakeData()
                msg_aggregator = self.msg_aggregator
                greenlet_manager = self.greenlet_manager
            self.migration_manager = DataMigrationManager(FakeRotki())  # type: ignore
            self.migration_manager.maybe_migrate_data()

        self.sync_rpc_nodes()
        ethereum_nodes = self.get_rpc_nodes(SupportedBlockchain.ETHEREUM, only_active=True)

        self.ethereum_inquirer = EthereumInquirer(
            greenlet_manager=self.greenlet_manager,
            connect_at_start=ethereum_nodes,
            database=self
        )

        self.ethereum_manager = EthereumManager(self.ethereum_inquirer)
        self.eth_transactions = EthereumTransactions(
                ethereum_inquirer=self.ethereum_inquirer, database=self
        )
        self.evm_tx_decoder = EthereumTransactionDecoder(
            database=self,
            ethereum_inquirer=self.ethereum_inquirer,
            transactions=self.eth_transactions,
            # msg_aggregator=self.msg_aggregator,
        )

        # if rpc_nodes:
        #     self.ethereum_manager.connect_to_multiple_nodes(rpc_nodes)

        self.inquirer.inject_evm_managers([(ChainID.ETHEREUM, self.ethereum_manager)])
        uniswap_v2_oracle = UniswapV2Oracle(self.ethereum_inquirer)
        uniswap_v3_oracle = UniswapV3Oracle(self.ethereum_inquirer)
        saddle_oracle = SaddleOracle(self.ethereum_inquirer)
        Inquirer().add_defi_oracles(
            uniswap_v2=uniswap_v2_oracle,
            uniswap_v3=uniswap_v3_oracle,
            saddle=saddle_oracle,
        )
        self.inquirer.set_oracles_order(self.get_settings().current_price_oracles)
        self.historian.set_oracles_order(self.get_settings().historical_price_oracles)
        self.beaconchain = BeaconChain(database=self, msg_aggregator=self.msg_aggregator)

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
        except AttributeError:
            # We swallow AttributeError here, because it occurs when self doesn't
            # have a `conn` attribute, i.e. we did not properly initialize. We want
            # to see the original error, and not the AttributeError in this case.
            pass

    def get_asset_by_symbol(self, symbol: str) -> Asset:
        # TODO: this indirection function could incorporate a custom mapping from yaml config
        return deserialize_asset(symbol)

    def get_main_currency(self):
        return self.get_settings().main_currency

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

    def get_settings(self, cursor=None, have_premium: bool = False) -> DBSettings:
        clean_settings = self.config.settings.dict().copy()

        clean_settings.pop('external_services', None)
        clean_settings.pop('rpc_nodes', None)
        clean_settings.pop('ignored_assets', None)

        # Remove None values
        for k in list(clean_settings):
            if clean_settings[k] is None:
                del clean_settings[k]

        return db_settings_from_dict(clean_settings, self.msg_aggregator)

    def sync_accounts(self, accounts: List[Account]) -> None:
        for account in accounts:
            if account.account_type != "ethereum":
                continue

            try:
                assert account.address is not None
                with self.user_write() as cursor:
                    logger.debug('Adding account to DB: %s', account)
                    self.add_blockchain_accounts(
                        write_cursor=cursor,
                        account_data=[
                            BlockchainAccountData(
                                address=account.address,
                                label=account.name,
                                chain=SupportedBlockchain.ETHEREUM,
                                tags=[]
                            )
                        ]
                    )
            except InputError:
                pass

    def get_eth_transactions(self, account: Account, with_receipts: bool = False) \
            -> List[Tuple[EvmTransaction, Optional[EvmTxReceipt]]]:

        assert account.account_type == "ethereum"
        address = cast(ChecksumEvmAddress, account.address)

        now = ts_now()

        self.sync_accounts([account])

        self.eth_transactions.single_address_query_transactions(
                address,
                start_ts=Timestamp(0),
                end_ts=now
        )

        dbevmtx = DBEvmTx(self)
        with self.conn.read_ctx() as cursor:
            txs, txs_total_count = dbevmtx.get_evm_transactions_and_limit_info(
                cursor=cursor,
                filter_=EvmTransactionsFilterQuery.make(accounts=[
                    EvmAccount(address, ChainID.ETHEREUM)
                ]),
                has_premium=False
            )
            assert len(txs) == txs_total_count

        result = []
        for txn in txs:
            receipt = None
            if with_receipts:
                receipt = self.eth_transactions.get_or_query_transaction_receipt(
                        txn.tx_hash
                )
            result.append((txn, receipt))

        return result

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

        ethereum_accounting_aggregator = EthereumAccountingAggregator(
            node_inquirer=self.ethereum_inquirer,
            msg_aggregator=self.msg_aggregator,
        )

        evm_accounting_aggregators = EVMAccountingAggregators(
            aggregators=[ethereum_accounting_aggregator]
            # TODO: add, optimism_accounting_aggregator],
        )

        return Accountant(
                db=self,
                msg_aggregator=self.msg_aggregator,
                evm_accounting_aggregators=evm_accounting_aggregators,
                premium=None
            )

    def get_blockchain_accounts(self, cursor=None) -> BlockchainAccounts:
        if self._active_eth_address:
            return BlockchainAccounts(eth=self._active_eth_address)
        return BlockchainAccounts()

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

    def get_actions_from_file(self, actions_file, include_trades=True) \
            -> List[Union[LedgerAction, HistoryBaseEntry]]:
        def safe_deserialize_ledger_action(action):
            if 'buy' in action or 'sell' in action:  # it is a Trade or AMMSwap
                if not include_trades:
                    return None
                return deserialize_trade(action)
            if 'spend_fee' in action:  # it is a HistoryBaseEntry
                return deserialize_event(action)
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
            -> List[Union[LedgerAction, HistoryBaseEntry]]:
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
                return self.get_actions_from_file(actions_file, include_trades=False)

        else:
            actions_file = self.data_directory / f'actions/{account.name}.yaml'
            if actions_file.exists():
                return self.get_actions_from_file(actions_file)

        return []

    def get_chains_aggregator(self, account: Account) -> ChainsAggregator:
        accs = {}  # type: ignore

        if account.account_type == "ethereum":
            accs['eth'] = [account.address]
        elif account.account_type == "bitcoin":
            accs['btc'] = [account.address]
        elif account.account_type == "bitcoincash":
            accs['bch'] = [account.address]
        else:
            raise ValueError('Unable to create chain manager for account')

        self.sync_accounts([account])

        # Eventually we should allow premium credentials in config file
        premium = False

        eth_modules = self.get_settings().active_modules
        if not premium:
            eth_modules = [mod for mod in eth_modules if mod not in PREMIUM_ONLY_ETH_MODULES]

        logger.debug('Creating ChainsAggregator with modules: %s', eth_modules)

        manager = ChainsAggregator(
            database=self,
            blockchain_accounts=BlockchainAccounts(**accs),
            beaconchain=self.beaconchain,
            data_directory=self.data_directory,
            ethereum_manager=self.ethereum_manager,
            polkadot_manager=None,
            avalanche_manager=None,
            kusama_manager=None,
            optimism_manager=None,
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

        exchange_opts = {
            'name': account_config.name,
            'api_key': str(account_config.api_key),
            'secret': str(account_config.secret).encode(),
            'database': self,
            'msg_aggregator': self.msg_aggregator
        }

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
            manager = self.get_chains_aggregator(account)

            ethereum_tokens = self.ethereum_manager.tokens
            ethereum_tokens.detect_tokens(
                only_cache=False,
                addresses=[account.address],
            )

            # This is a little hack because query_balances sometimes hooks back
            # into out get_blockchain_accounts() without providing context (for
            # example from makerdao module).
            self._active_eth_address = account.address
            manager.query_balances(
                blockchain=SupportedBlockchain.ETHEREUM
            )
            self._active_eth_address = None

            return reduce(operator.add, manager.balances.eth.values())

        if account.account_type == "bitcoin":
            manager = self.get_chains_aggregator(account)
            manager.query_balances()
            btc = Asset('BTC')

            return BalanceSheet(assets={
                btc: reduce(operator.add, manager.balances.btc.values())
            }, liabilities={})

        if account.account_type == "bitcoincash":
            manager = self.get_chains_aggregator(account)
            manager.query_balances()
            bch = Asset('BCH')

            return BalanceSheet(assets={
                bch: reduce(operator.add, manager.balances.bch.values())
            }, liabilities={})

        if account.account_type == "file":
            return self.get_balances_from_file(
                os.path.join(self.data_directory, account.config.file)
            )

        logger.warning(
            'Returning empty BalanceSheet because account type "%s" is not supported yet.',
            account.account_type
        )

        return BalanceSheet(assets={}, liabilities={})

    def query_nfts(self, account: Account) -> List[Nfts]:
        if account.account_type == "ethereum":
            manager = self.get_chains_aggregator(account)
            nfts = manager.get_module('nfts')
            nft_result = nfts.get_all_info(addresses=[account.address], ignore_cache=True)
            if account.address in nft_result.addresses:
                return nft_result.addresses[account.address]
        return []

    def fetch_balances(self, account: Account):
        query_sheet = self.query_balances(account)
        logger.debug('Balances for %s before annotations: %s', account.name, query_sheet)
        path = self.annotations_directory / (account.name + '.yaml')
        if path.exists():
            query_sheet += self.get_balances_from_file(path)
        self.write_balances(account, query_sheet)

    def get_balances(self, account: Account) -> BalanceSheet:
        path = self.balances_directory / (account.name + '.yaml')
        if path.exists():
            return self.get_balances_from_file(path)
        return BalanceSheet(assets={}, liabilities={})

    def get_balances_from_file(self, path) -> BalanceSheet:
        with open(path, 'r') as account_f:
            account = yaml.load(account_f, Loader=yaml.SafeLoader)

        assets = {}  # type: Dict[Asset, Balance]
        liabilities = {}  # type: Dict[Asset, Balance]

        if 'assets' in account:
            for balance in account['assets']:
                try:
                    balance, asset = deserialize_balance(balance, self)
                except UnknownAsset as e:
                    logger.warning(str(e))
                    continue
                if asset in assets:
                    assets[asset] += balance
                else:
                    assets[asset] = balance

        if 'liabilities' in account:
            for balance in account['liabilities']:
                try:
                    balance, asset = deserialize_balance(balance, self)
                except UnknownAsset as e:
                    logger.warning(str(e))
                    continue
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

            if not balances.liabilities and 'liabilities' in contents:
                del contents['liabilities']

            if not balances.assets and 'assets' in contents:
                del contents['assets']

            yaml.dump(contents, stream=balances_file, sort_keys=True)

    # def get_amm_swaps(
    #         self,
    #         cursor,
    #         from_ts: Optional[Timestamp] = None,
    #         to_ts: Optional[Timestamp] = None,
    #         location: Optional[Location] = None,
    #         address: Optional[ChecksumEvmAddress] = None,
    # ) -> List[AMMSwap]:
    #     return self._amm_swaps
    #
    # def add_amm_swaps(self, write_cursor, swaps: List[AMMSwap]) -> None:
    #     self._amm_swaps = []
    #     self._amm_swaps.extend(swaps)

    def update_used_query_range(
            self,
            write_cursor,
            name: str,
            start_ts: Timestamp,
            end_ts: Timestamp
    ) -> None:
        pass

    def update_used_block_query_range(
            self,
            write_cursor,
            name: str,
            from_block: int,
            to_block: int
    ) -> None:
        pass

    def get_used_query_range(self, cursor, name: str) -> Optional[Tuple[Timestamp, Timestamp]]:
        return None

    def get_ignored_action_ids(
            self,
            cursor,
            action_type: Optional[ActionType],
            ) -> Dict[ActionType, List[str]]:
        return {}

    # def add_asset_identifiers(self, asset_identifiers: List[str]) -> None:
    #     pass

    def get_binance_pairs(self, name: str, location: Location) -> List[str]:
        return []

    def perform_assets_updates(self):
        self.assets_updater.perform_update(None, None)

        try:
            update_spam_assets(db=self, assets_info=[])
        except UnknownAsset as e:
            logger.warning(str(e))

        self.sync_config_assets()

    def sync_rpc_nodes(self):
        'Ensures that the database matches the config file'

        with self.user_write() as cursor:
            # Not the best solution but the easiest to implement :blush:
            cursor.execute('DELETE FROM rpc_nodes;')
            read_and_write_nodes_in_database(cursor)

        settings_rpc_nodes = list(self.config.settings.rpc_nodes or [])
        db_rpc_nodes = list(self.get_rpc_nodes(SupportedBlockchain.ETHEREUM))

        for db_rpc_node in db_rpc_nodes:
            if db_rpc_node.node_info.owned:  # do not delete preconfigured nodes
                if db_rpc_node.node_info.name in [n.name for n in settings_rpc_nodes]:
                    # TODO: should update web3 node in db if necessary
                    settings_rpc_nodes = [
                        n for n in settings_rpc_nodes if n.name != db_rpc_node.node_info.name
                    ]
                else:
                    self.delete_rpc_node(
                            db_rpc_node.identifier,
                            blockchain=SupportedBlockchain.ETHEREUM
                    )

        for rpc_node in settings_rpc_nodes:
            self.add_rpc_node(
                WeightedNode(
                    identifier=rpc_node.name,
                    node_info=NodeName(
                        name=rpc_node.name,
                        endpoint=rpc_node.endpoint,
                        blockchain=SupportedBlockchain.ETHEREUM,
                        owned=True,
                    ),
                    weight=FVal(0.4),
                    active=True,
                )
            )

    def sync_config_assets(self):
        'Sync assets defined in config with database'

        for token in self.config.tokens:
            eth_token = deserialize_evm_token(token.dict())
            identifier = 'eip155:1/erc20:' + eth_token.evm_address

            try:
                evm_token = self.globaldb.get_evm_token(eth_token.evm_address, eth_token.chain_id)
                if evm_token is None:
                    raise UnknownAsset(eth_token.evm_address)
                logger.debug('Asset already exists: %s', evm_token)

                # This could be more involved
                if eth_token.coingecko and eth_token.coingecko != evm_token.coingecko:
                    logger.info('Updating asset db for token: %s', eth_token)
                    self.globaldb.edit_evm_token(eth_token)

                if eth_token.decimals and eth_token.decimals != evm_token.decimals:
                    logger.info('Updating asset db for token: %s', eth_token)
                    self.globaldb.edit_evm_token(eth_token)

            except UnknownAsset:
                self.globaldb.add_asset(identifier, AssetType.EVM_TOKEN, eth_token)
                try:
                    self.get_asset_by_symbol(identifier)
                except UnknownAsset as exc:
                    raise ValueError('Unable to add asset: ' + str(eth_token)) from exc

            self.asset_resolver.clean_memory_cache()

        with self.conn.read_ctx() as cursor:
            ignored_assets = {asset.identifier for asset in self.get_ignored_assets(cursor)}

        for ignored_asset in self.config.settings.ignored_assets:

            token_identifier = deserialize_identifier(ignored_asset)

            if token_identifier in ignored_assets:
                continue

            if ':' in token_identifier:
                token_address = token_identifier.split(':')[-1]
            else:
                token_address = token_identifier

            try:
                token = get_or_create_evm_token(
                    userdb=self,
                    evm_address=token_address,
                    chain_id=ChainID.ETHEREUM,
                    protocol=SPAM_PROTOCOL,
                    decimals=18,
                )
            except InputError as exc:
                logger.warning('Unable to add ignored asset: %s', str(exc))
                continue

            logger.debug('Adding to ignored assets: %s', token)
            with self.user_write() as cursor:
                self.add_to_ignored_assets(write_cursor=cursor, asset=token)

    def sync_manual_prices(self):
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
