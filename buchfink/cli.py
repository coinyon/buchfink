import logging
import os.path
import shutil
from datetime import datetime
from operator import attrgetter, itemgetter
from typing import List

import click
import coloredlogs
import yaml
from rotkehlchen.constants import ZERO
from rotkehlchen.utils.misc import ts_now
from tabulate import tabulate

from buchfink.datatypes import Asset, FVal, Trade
from buchfink.db import BuchfinkDB
from buchfink.serialization import (serialize_ledger_actions,
                                    serialize_timestamp, serialize_trades)

from .classification import classify_tx
from .config import ReportConfig
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

    target_config = os.path.join(directory, 'buchfink.yaml')

    if os.path.exists(target_config):
        click.echo(click.style('Already initialized (buchfink.yaml exists), aborting.', fg='red'))
        return

    initial_config = os.path.join(os.path.dirname(__file__), 'data', 'buchfink.initial.yaml')
    shutil.copyfile(initial_config, target_config)

    buchfink_db = BuchfinkDB(directory)

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
@click.option('--fetch/--no-fetch', default=True, help='Fetch balances from sources')
@click.option(
        '--minimum-balance',
        '-m',
        type=float,
        default=0.0,
        help='Hide balances smaller than this amount (default 0)'
)
def balances(keyword, minimum_balance, fetch):
    "Show balances across all accounts"

    buchfink_db = BuchfinkDB()
    assets_sum = {}
    assets_usd_sum = {}
    liabilities_sum = {}
    liabilities_usd_sum = {}

    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        if fetch:
            sheet = buchfink_db.query_balances(account)
            buchfink_db.write_balances(account, sheet)
        else:
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

    currency = buchfink_db.get_main_currency()
    currency_in_usd = buchfink_db.inquirer.find_usd_price(currency)

    table = []
    assets = [obj[0] for obj in sorted(assets_usd_sum.items(), key=itemgetter(1), reverse=True)]
    balance_in_currency_sum = 0

    for asset in assets:
        balance = assets_sum[asset]
        balance_in_currency = assets_usd_sum.get(asset, FVal(0)) / currency_in_usd
        if balance > ZERO and balance_in_currency >= FVal(minimum_balance):
            balance_in_currency_sum += balance_in_currency
            table.append([asset, balance, asset.symbol, round(float(balance_in_currency), 2)])
    table.append(['Total', None, None, round(float(balance_in_currency_sum), 2)])
    print(tabulate(table, headers=[
        'Asset',
        'Amount',
        'Symbol',
        'Fiat Value (%s)' % currency.symbol
    ]))

    if liabilities_sum:
        table = []
        balance_in_currency_sum = 0
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
                table.append([asset, balance, asset.symbol, round(float(balance_in_currency), 2)])
        table.append(['Total', None, None, round(float(balance_in_currency_sum), 2)])
        print()
        print(tabulate(table, headers=[
            'Liability',
            'Amount',
            'Symbol',
            'Fiat Value (%s)' % currency.symbol
        ]))


@buchfink.command('fetch')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
def fetch_(keyword, account_type):
    "Fetch trades for configured accounts"

    buchfink_db = BuchfinkDB()
    now = ts_now()

    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        if account_type is not None and account_type not in account.account_type:
            continue

        name = account.name

        if account.account_type == "ethereum":

            click.echo('Analyzing ethereum transactions for ' + name)

            manager = buchfink_db.get_chain_manager(account)
            txs = manager.ethereum.transactions.single_address_query_transactions(account.address,
                    start_ts=0,
                    end_ts=now,
                    with_limit=False)

            all_actions = []
            for txn in txs:
                tx_hash = '0x' + txn.tx_hash.hex()
                receipt = buchfink_db.get_ethereum_transaction_receipt(tx_hash, manager)

                actions = classify_tx(account, tx_hash, txn, receipt)
                if actions:
                    print(actions)
                all_actions.extend(actions)

            logger.info('Fetched %d action from %s', len(all_actions), name)

            if all_actions:
                with open("actions/" + name + ".yaml", "w") as yaml_file:
                    yaml.dump({"actions": serialize_ledger_actions(all_actions)}, stream=yaml_file)

            click.echo('Fetching uniswap trades for ' + name)

            manager = buchfink_db.get_chain_manager(account)

            trades = manager.eth_modules['uniswap'].get_trades(
                    addresses=manager.accounts.eth,
                    from_timestamp=int(epoch_start_ts),
                    to_timestamp=int(epoch_end_ts)
                )

        elif account.account_type == "exchange":

            click.echo('Fetching trades for ' + name)

            exchange = buchfink_db.get_exchange(name)

            api_key_is_valid, error = exchange.validate_api_key()

            if not api_key_is_valid:
                logger.critical(
                        'Skipping exchange %s because API key is not valid (%s)',
                        account.name,
                        error
                )
                continue

            trades = exchange.query_online_trade_history(
                start_ts=epoch_start_ts,
                end_ts=epoch_end_ts
            )

        else:
            logger.debug('No way to retrieve trades for %s, yet', name)
            continue

        logger.info('Fetched %d trades from %s', len(trades), name)

        with open("trades/" + name + ".yaml", "w") as yaml_file:
            yaml.dump({"trades": serialize_trades(trades)}, stream=yaml_file)

        sheet = buchfink_db.query_balances(account)
        buchfink_db.write_balances(account, sheet)

        logger.info('Fetched balances from %s', name)


@buchfink.command('report')
@click.option('--name', '-n', type=str, required=True)
@click.option('--from', '-f', 'from_date', type=str, required=True)
@click.option('--to', '-t', 'to_date', type=str, required=True)
def report_(name, from_date, to_date):
    "Run an ad-hoc report on your data"

    buchfink_db = BuchfinkDB()

    result = run_report(buchfink_db, ReportConfig(
        name=name,
        from_dt=datetime.fromisoformat(from_date),
        to_dt=datetime.fromisoformat(to_date)
    ))

    logger.info("Overview: %s", result['overview'])


@buchfink.command('trades')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--asset', '-a', type=str, default=None, help='Filter by asset')
def trades_(keyword, asset):
    "Show trades"

    buchfink_db = BuchfinkDB()

    trades: List[Trade] = []
    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        trades.extend(buchfink_db.get_local_trades_for_account(account.name))

    if asset is not None:
        the_asset = Asset(asset)
        trades = [trade for trade in trades if the_asset in (trade.base_asset, trade.quote_asset)]

    trades = sorted(trades, key=attrgetter('timestamp'))

    if trades:
        table = []
        for trade in trades:
            table.append([
                serialize_timestamp(trade.timestamp),
                str(trade.trade_type),
                str(trade.amount),
                str(trade.base_asset.symbol),
                str(trade.amount * trade.rate),
                str(trade.quote_asset.symbol),
                str(trade.rate),
            ])
        print(tabulate(table, headers=[
            'Time',
            'Type',
            'Amount',
            'Quote Asset',
            'Amount',
            'Base Asset',
            'Rate'
        ]))


@buchfink.command()
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
def run(keyword):
    "Generate reports for all report definition and output overview table"

    buchfink_db = BuchfinkDB()

    num_matched_reports = 0
    results = {}

    for report in buchfink_db.get_all_reports():
        name = str(report.name)

        if keyword is not None and keyword not in name:
            continue
        num_matched_reports += 1

        results[name] = run_report(buchfink_db, report)

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
    currency_in_usd = buchfink_db.inquirer.find_usd_price(currency)

    accountant.process_history(epoch_start_ts, epoch_end_ts, all_trades, [], [], [], [], [])
    total_usd = FVal(0)
    table = []

    raise NotImplementedError()
    """
    # TODO: must be adapted to current rotki api
    for (symbol, (_allowance, buy_price)) in accountant.events.details.items():
        symbol_usd = buchfink_db.inquirer.find_usd_price(symbol)
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


if __name__ == '__main__':
    buchfink()  # pylint: disable=no-value-for-parameter
