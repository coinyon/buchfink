import logging
import os.path
import re
import shutil
import sys
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from typing import List, Optional, Tuple

import click
import coloredlogs
import yaml
from rotkehlchen.chain.ethereum.trades import AMMTrade
from rotkehlchen.constants import ZERO
from rotkehlchen.history.price import PriceHistorian
from rotkehlchen.utils.misc import ts_now
from tabulate import tabulate

from buchfink.datatypes import FVal, LedgerAction, Trade
from buchfink.db import BuchfinkDB
from buchfink.serialization import (deserialize_timestamp,
                                    serialize_ledger_actions,
                                    serialize_timestamp, serialize_trades)

from .classification import classify_tx
from .importers import zerion_csv
from .models import Account, ReportConfig, FetchConfig
from .models.account import account_from_string
from .report import run_report

logger = logging.getLogger(__name__)

epoch_start_ts = datetime(2011, 1, 1).timestamp()
epoch_end_ts = datetime(2031, 1, 1).timestamp()


@click.group()
@click.option('--log-level', '-l', type=str, default='INFO')
def buchfink(log_level):
    coloredlogs.install(level=log_level, fmt='%(asctime)s %(levelname)s %(message)s')


@buchfink.command()
@click.option('--directory', '-d', type=str, default='.')
def init(directory):
    "Initialize new Buchfink directory"

    bf_dir = Path(directory).absolute()
    logger.debug('Initializing in %s', str(bf_dir))
    target_config = bf_dir / 'buchfink.yaml'
    init_data = Path(__file__).parent / 'data' / 'init'

    if target_config.exists():
        click.echo(click.style(
            f'Already initialized (buchfink.yaml exists in {bf_dir}), aborting.',
            fg='red'
        ))
        sys.exit(1)

    for init_file in init_data.iterdir():
        logger.debug('Copying %s', init_file.name)
        shutil.copyfile(init_file, bf_dir / init_file.name)

    buchfink_db = BuchfinkDB(bf_dir)

    click.echo(
        click.style('Successfully initialized in {0}.'.format(
                buchfink_db.data_directory.absolute()
            ), fg='green')
    )


@buchfink.command('list')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@click.option('--output', '-o', type=str, default=None, help='Output field')
def list_(keyword, account_type, output):
    "List accounts"
    buchfink_db = BuchfinkDB()

    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        if account_type is not None and account_type not in account.account_type:
            continue

        if output is None:
            type_and_name = '{0}: {1}'.format(
                    account.account_type,
                    click.style(account.name, fg='green')
            )
            address = ' ({0})'.format(account.address) if account.address is not None else ''
            click.echo(type_and_name + address)
        else:
            click.echo('{0}'.format(getattr(account, output)))


@buchfink.command()
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--external', '-e', type=str, multiple=True,
        help='Use adhoc / external account')
@click.option('--total', is_flag=True, help='Only show totals')
@click.option('--denominate-asset', '-d', type=str, help='Denominate in this asset')
@click.option('--fetch', '-f', is_flag=True, help='Fetch balances from sources')
@click.option(
        '--minimum-balance',
        '-m',
        type=float,
        default=0.0,
        help='Hide balances smaller than this amount (default 0)'
)
def balances(keyword, minimum_balance, fetch, total, external, denominate_asset):
    "Show balances across all accounts"

    buchfink_db = BuchfinkDB()
    assets_sum = {}
    assets_usd_sum = {}
    liabilities_sum = {}
    liabilities_usd_sum = {}

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = buchfink_db.get_all_accounts()

    if fetch:
        buchfink_db.perform_assets_updates()

    for account in accounts:
        if keyword is not None and keyword not in account.name:
            continue

        if fetch:
            buchfink_db.fetch_balances(account)

        sheet = buchfink_db.get_balances(account)

        for asset, balance in sheet.assets.items():
            amount = balance.amount
            assets_sum[asset] = assets_sum.get(asset, FVal(0)) + amount
            assets_usd_sum[asset] = assets_usd_sum.get(asset, FVal(0)) + balance.usd_value

        for liability, balance in sheet.liabilities.items():
            amount = balance.amount
            liabilities_sum[liability] = liabilities_sum.get(liability, FVal(0)) + amount
            liabilities_usd_sum[liability] = liabilities_usd_sum.get(liability, FVal(0)) \
                    + balance.usd_value

    if denominate_asset is not None:
        currency = buchfink_db.get_asset_by_symbol(denominate_asset)
    else:
        currency = buchfink_db.get_main_currency()

    currency_in_usd = FVal(buchfink_db.inquirer.find_usd_price(currency))
    logger.debug('Denominating in %s: %s USD', currency, currency_in_usd)
    table = []
    assets = [obj[0] for obj in sorted(assets_usd_sum.items(), key=itemgetter(1), reverse=True)]
    balance_in_currency_sum = 0
    small_balances_sum = 0

    for asset in assets:
        balance = assets_sum[asset]
        balance_in_currency = FVal(assets_usd_sum.get(asset, 0)) / currency_in_usd
        if balance > ZERO:
            if balance_in_currency > FVal(minimum_balance):
                table.append([
                    asset.name,
                    balance,
                    asset.symbol,
                    round(float(balance_in_currency), 2)
                ])
            else:
                small_balances_sum += balance_in_currency
            balance_in_currency_sum += balance_in_currency

    if total:
        print(f'Total assets: {round(float(balance_in_currency_sum), 2)} {currency.symbol}')

    else:
        if small_balances_sum > 0:
            table.append(['Others', None, None, round(float(small_balances_sum), 2)])

        table.append(['Total', None, None, round(float(balance_in_currency_sum), 2)])
        print(tabulate(table, headers=[
            'Asset',
            'Amount',
            'Symbol',
            'Value (%s)' % currency.symbol
        ]))

    if liabilities_sum:
        table = []
        balance_in_currency_sum = 0
        small_balances_sum = 0
        assets = [
                obj[0]
                for obj
                in sorted(liabilities_usd_sum.items(), key=itemgetter(1), reverse=True)
        ]
        for asset in assets:
            balance = liabilities_sum[asset]
            balance_in_currency = liabilities_usd_sum.get(asset, FVal(0)) / currency_in_usd
            if balance > ZERO and balance_in_currency >= FVal(minimum_balance):
                balance_in_currency_sum += balance_in_currency
                table.append([
                    asset.name,
                    balance,
                    asset.symbol,
                    round(float(balance_in_currency), 2)
                ])
            else:
                small_balances_sum += balance_in_currency
        table.append(['Total', None, None, round(float(balance_in_currency_sum), 2)])

        if total:
            print(
                f'Total liabilities: '
                f'{round(float(balance_in_currency_sum), 2)} {currency.symbol}'
            )

        else:
            if small_balances_sum > 0:
                table.append(['Others', None, None, round(float(small_balances_sum), 2)])

            print()
            print(tabulate(table, headers=[
                'Liability',
                'Amount',
                'Symbol',
                'Value (%s)' % currency.symbol
            ]))


@buchfink.command('fetch')
@click.option('--external', '-e', type=str, multiple=True,
        help='Use adhoc / external account')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@click.option('--actions', 'fetch_actions', is_flag=True, help='Fetch actions only')
@click.option('--balances', 'fetch_balances', is_flag=True, help='Fetch balances only')
@click.option('--trades', 'fetch_trades', is_flag=True, help='Fetch trades only')
def fetch_(keyword, account_type, fetch_actions, fetch_balances, fetch_trades, external):
    "Fetch trades for configured accounts"

    buchfink_db = BuchfinkDB()
    buchfink_db.perform_assets_updates()
    now = ts_now()
    fetch_limited = fetch_actions or fetch_balances or fetch_trades

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = buchfink_db.get_all_accounts()

    # TODO: This should move to BuchfinkDB.get_accounts()
    if keyword is not None:
        if keyword.startswith('/') and keyword.endswith('/'):
            keyword_re = re.compile(keyword[1:-1])
            accounts = [acc for acc in accounts if keyword_re.search(acc.name)]
        else:
            accounts = [acc for acc in accounts if keyword in acc.name]

    logger.info(
            'Collected %d account(s): %s',
            len(accounts),
            ', '.join([acc.name for acc in accounts])
        )

    for account in accounts:
        if account_type is not None and account_type not in account.account_type:
            continue

        name = account.name
        trades = []
        actions = []
        fetch_config = account.config.fetch or FetchConfig()

        fetch_actions_for_this_account = (not fetch_limited or fetch_actions) and \
                fetch_config.actions

        fetch_balances_for_this_account = (not fetch_limited or fetch_balances) and \
                fetch_config.balances

        fetch_trades_for_this_account = (not fetch_limited or fetch_trades) and \
                fetch_config.trades

        if account.account_type == "ethereum":

            if fetch_actions_for_this_account:
                logger.info('Analyzing ethereum transactions for %s', name)
                manager = buchfink_db.get_chain_manager(account)

                txs = manager.ethereum.transactions.single_address_query_transactions(
                        account.address,
                        start_ts=0,
                        end_ts=now,
                        with_limit=False,
                        only_cache=False
                )

                for txn in txs:
                    tx_hash = '0x' + txn.tx_hash.hex()
                    receipt = buchfink_db.get_ethereum_transaction_receipt(tx_hash, manager)

                    acc_actions = classify_tx(account, tx_hash, txn, receipt)
                    if actions:
                        for act in actions:
                            logger.debug('Found action: %s', act)
                    actions.extend(acc_actions)

            if fetch_trades_for_this_account:
                logger.info('Fetching trades for %s', name)

                manager = buchfink_db.get_chain_manager(account)

                trades = manager.eth_modules['uniswap'].get_trades(
                        addresses=manager.accounts.eth,
                        from_timestamp=int(epoch_start_ts),
                        to_timestamp=int(epoch_end_ts),
                        only_cache=False
                    )

                trades.extend(zerion_csv.get_trades(account))

        elif account.account_type == "exchange":

            if fetch_trades_for_this_account:
                logger.info('Fetching exhange trades for %s', name)

                exchange = buchfink_db.get_exchange(name)

                api_key_is_valid, error = exchange.validate_api_key()

                if not api_key_is_valid:
                    logger.critical(
                            'Skipping exchange %s because API key is not valid (%s)',
                            account.name,
                            error
                    )

                else:
                    trades = exchange.query_online_trade_history(
                        start_ts=epoch_start_ts,
                        end_ts=epoch_end_ts
                    )

        else:
            logger.debug('No way to retrieve trades for %s, yet', name)

        annotations_path = "annotations/" + name + ".yaml"

        if fetch_actions_for_this_account:

            if os.path.exists(annotations_path):
                annotated = buchfink_db.get_actions_from_file(annotations_path)
            else:
                annotated = []

            logger.info('Fetched %d action(s) (%d annotated) from %s',
                    len(actions) + len(annotated), len(annotated), name)
            actions.extend(annotated)

            if actions:
                with open(buchfink_db.actions_directory / (name + ".yaml"), "w") as yaml_file:
                    yaml.dump({
                        "actions": serialize_ledger_actions(actions)
                    }, stream=yaml_file, sort_keys=True)

        if fetch_trades_for_this_account:
            if os.path.exists(annotations_path):
                annotated = buchfink_db.get_trades_from_file(annotations_path)
            else:
                annotated = []

            logger.info('Fetched %d trades(s) (%d annotated) from %s',
                    len(trades) + len(annotated), len(annotated), name)

            trades.extend(annotated)

            existing = set()
            unique_trades = []
            for trade in trades:
                if isinstance(trade, AMMTrade):
                    unique_trades.append(trade)
                    for swap in trade.swaps:
                        existing.add((swap.location, swap.tx_hash))
                elif not (trade.location, trade.link) in existing:
                    existing.add((trade.location, trade.link))
                    unique_trades.append(trade)
                else:
                    logger.warning('Removing duplicate trade: %s', trade)

            with open(buchfink_db.trades_directory / (name + ".yaml"), "w") as yaml_file:
                yaml.dump({
                    "trades": serialize_trades(unique_trades)
                }, stream=yaml_file, sort_keys=True)

        if fetch_balances_for_this_account:
            buchfink_db.fetch_balances(account)
            logger.info('Fetched balances from %s', name)


@buchfink.command()
@click.option('--external', '-e', type=str, multiple=True,
        help='Use adhoc / external account')
@click.option('--name', '-n', type=str, required=True)
@click.option('--from', '-f', 'from_date', type=str, required=True)
@click.option('--to', '-t', 'to_date', type=str, required=True)
def run(name, from_date, to_date, external):
    "Run a full fetch + report cycle"

    buchfink_db = BuchfinkDB()

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = buchfink_db.get_all_accounts()

    result = run_report(buchfink_db, accounts, ReportConfig(
        name=name,
        from_dt=datetime.fromisoformat(from_date),
        to_dt=datetime.fromisoformat(to_date)
    ))

    logger.info("Overview: %s", result['overview'])


@buchfink.command('trades')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--asset', '-a', type=str, default=None, help='Filter by asset')
@click.option('--fetch', '-f', is_flag=True, help='Fetch trades from sources')
def trades_(keyword, asset, fetch):  # pylint: disable=unused-argument
    "Show trades"

    buchfink_db = BuchfinkDB()

    trades: List[Tuple[Trade, Account]] = []
    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        trades.extend(
                (trade, account)
                for trade in buchfink_db.get_local_trades_for_account(account.name)
                )

    if asset is not None:
        the_asset = buchfink_db.get_asset_by_symbol(asset)
        trades = [
                trade
                for trade in trades
                if the_asset in (trade[0].base_asset, trade[0].quote_asset)
                ]

    trades = sorted(trades, key=lambda trade_account: trade_account[0].timestamp)

    if trades:
        table = []
        for (trade, account) in trades:
            table.append([
                serialize_timestamp(trade.timestamp),
                str(trade.trade_type),
                str(trade.amount),
                str(trade.base_asset.symbol),
                str(trade.amount * trade.rate),
                str(trade.quote_asset.symbol),
                str(trade.rate),
                str(account.name)
            ])
        print(tabulate(table, headers=[
            'Time',
            'Type',
            'Amount',
            'Quote Asset',
            'Amount',
            'Base Asset',
            'Rate',
            'Account'
        ]))


@buchfink.command('actions')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--asset', '-a', type=str, default=None, help='Filter by asset')
def actions_(keyword, asset):
    "Show actions"

    buchfink_db = BuchfinkDB()

    actions: List[Tuple[LedgerAction, Account]] = []
    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        actions.extend(
                (action, account)
                for action in buchfink_db.get_local_ledger_actions_for_account(account.name)
                )

    if asset is not None:
        the_asset = buchfink_db.get_asset_by_symbol(asset)
        actions = [action for action in actions if the_asset in (action[0].asset,)]

    actions = sorted(actions, key=lambda action_account: action_account[0].timestamp)

    if actions:
        table = []
        for (action, account) in actions:
            table.append([
                serialize_timestamp(action.timestamp),
                str(action.action_type),
                str(action.amount),
                str(action.asset.symbol),
                str(account.name),
            ])
        print(tabulate(table, headers=[
            'Time',
            'Type',
            'Amount',
            'Asset',
            'Account'
        ]))


@buchfink.command('report')
@click.option('--external', '-e', type=str, multiple=True,
        help='Use adhoc / external account')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--report', type=str, default=None, help='Filter by keyword in report name')
@click.option('--year', type=int, default=None, help='Run adhoc-report for given year',
        multiple=True)
def report_(keyword, external, report, year):
    "Generate reports for all report definition and output overview table"

    buchfink_db = BuchfinkDB()

    results = {}

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = [account for account in buchfink_db.get_all_accounts()
                if keyword is None or keyword in account.name]

    if year:
        reports = [ReportConfig(
            name=f'adhoc-{_year}',
            title=str(year),
            template=None,
            from_dt=datetime(_year, 1, 1),
            to_dt=datetime(_year + 1, 1, 1)
            ) for _year in year]
    else:
        reports = [
            report_ for report_ in buchfink_db.get_all_reports()
            if report is None or report in report_.name
        ]

    for _report in reports:
        name = str(_report.name)
        results[name] = run_report(buchfink_db, accounts, _report)

    table = []
    for report_name, result in results.items():
        table.append([
            report_name,
            result['overview']['total_profit_loss'],
            result['overview']['total_taxable_profit_loss']
        ])
    print(tabulate(table, headers=['Report', 'Profit/Loss', 'Taxable P/L']))


@buchfink.command()
def allowances():
    # pylint: disable = W
    "Show the amount of each asset that you could sell tax-free"

    buchfink_db = BuchfinkDB()

    num_matched_accounts = 0
    all_trades = []

    for account in buchfink_db.get_all_accounts():
        num_matched_accounts += 1
        all_trades.extend(buchfink_db.get_local_trades_for_account(account.name))

    logger.info('Collected %d trades from %d exchange account(s)',
            len(all_trades), num_matched_accounts)

    accountant = buchfink_db.get_accountant()
    currency = buchfink_db.get_main_currency()
    currency_in_usd = FVal(buchfink_db.inquirer.find_usd_price(currency))

    accountant.process_history(epoch_start_ts, epoch_end_ts, all_trades, [], [], [], [], [])
    total_usd = FVal(0)
    table = []

    raise NotImplementedError()
    """
    # TODO: must be adapted to current rotki api
    for (symbol, (_allowance, buy_price)) in accountant.events.details.items():
        symbol_usd = FVal(buchfink_db.inquirer.find_usd_price(symbol))
        total_usd += _allowance * symbol_usd
        table.append([
            symbol,
            _allowance,
            round(float(_allowance * symbol_usd / currency_in_usd), 2),
            symbol_usd / currency_in_usd,
            buy_price
        ])
    table.append(['Total', None, round(float(total_usd / currency_in_usd), 2), None, None])
    print(tabulate(table, headers=[
        'Asset',
        'Tax-free allowance',
        'Tax-free amount (%s)' % currency.symbol,
        'Current price (%s)' % currency.symbol,
        'Average buy price (%s)' % currency.symbol
    ]))
    """


@buchfink.command('quote')
@click.argument('asset', nargs=-1)
@click.option('--amount', '-n', type=float, default=1.0)
@click.option('--timestamp', '-t', type=str, default=None)
@click.option('--base-asset', '-b', 'base_asset_', type=str, default=None)
def quote(asset: Tuple[str], amount: float, base_asset_: Optional[str], timestamp: Optional[str]):
    """
    Show a price quote. In addition to the options flags, the following short syntax
    is also supported:

        buchfink quote 100 ETH

        buchfink quote ETH/BTC

        buchfink quote 2.5 ETH/BTC
    """
    buchfink_db = BuchfinkDB()
    buchfink_db.perform_assets_updates()
    base_asset = buchfink_db.get_asset_by_symbol(base_asset_) \
            if base_asset_ \
            else buchfink_db.get_main_currency()
    base_in_usd = FVal(buchfink_db.inquirer.find_usd_price(base_asset))
    a_usd = buchfink_db.get_asset_by_symbol('USD')

    ds_timestamp = deserialize_timestamp(timestamp) if timestamp else None
    historian = PriceHistorian()

    for symbol in asset:
        try:
            amount = float(symbol)
            continue
        except ValueError:
            pass
        if '/' in symbol:
            symbol, base_symbol = symbol.split('/')
            base_asset = buchfink_db.get_asset_by_symbol(base_symbol)
            base_in_usd = FVal(buchfink_db.inquirer.find_usd_price(base_asset))
        asset_ = buchfink_db.get_asset_by_symbol(symbol)
        if ds_timestamp:
            asset_usd = historian.query_historical_price(
                    from_asset=asset_,
                    to_asset=a_usd,
                    timestamp=ds_timestamp
            )
        else:
            asset_usd = FVal(buchfink_db.inquirer.find_usd_price(asset_))
        click.echo('{} {} = {} {}'.format(
                click.style(f'{amount}', fg='white'),
                click.style(asset_.symbol, fg='green'),
                click.style(f'{FVal(amount) * asset_usd / base_in_usd}', fg='white'),
                click.style(base_asset.symbol, fg='green')
        ))


@buchfink.command('cache')
@click.argument('asset', nargs=-1)
@click.option('--base-asset', '-b', 'base_asset_', type=str, default=None)
def cache(asset: Tuple[str], base_asset_: Optional[str]):
    """
    Build a historical price cache
    """
    buchfink_db = BuchfinkDB()
    base_asset = buchfink_db.get_asset_by_symbol(base_asset_) \
            if base_asset_ \
            else buchfink_db.get_main_currency()

    for symbol in asset:
        asset_ = buchfink_db.get_asset_by_symbol(symbol)
        buchfink_db.cryptocompare.create_cache(asset_, base_asset, False)


if __name__ == '__main__':
    buchfink()  # pylint: disable=no-value-for-parameter
