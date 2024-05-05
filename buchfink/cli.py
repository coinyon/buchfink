import logging
import os
import os.path
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from functools import update_wrapper
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import click
import coloredlogs
import pyqrcode
import yaml
from rich.progress import track
from rotkehlchen.constants import ZERO
from rotkehlchen.errors.asset import WrongAssetType
from rotkehlchen.errors.misc import RemoteError
from rotkehlchen.history.price import PriceHistorian
from rotkehlchen.utils.misc import ts_ms_to_sec, ts_now
from tabulate import tabulate
from web3.exceptions import CannotHandleRequest

from buchfink.datatypes import AssetType, FVal, HistoryBaseEntry, HistoryEvent, Timestamp, Trade
from buchfink.db import BuchfinkDB
from buchfink.serialization import (
    deserialize_asset,
    deserialize_timestamp,
    serialize_decimal,
    serialize_nfts,
    serialize_timestamp,
)

from .models import Account, FetchConfig, ReportConfig
from .models.account import account_from_string
from .report import render_report, run_report
from .tasks import fetch_actions, fetch_trades, write_actions, write_trades

if TYPE_CHECKING:
    from typing import Dict  # noqa: F401

    from buchfink.datatypes import Asset  # noqa: F401

logger = logging.getLogger(__name__)


def _get_accounts(
    buchfink_db: BuchfinkDB, external=None, exclude=None, keyword=None, account_type=None
) -> List[Account]:
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

    if exclude is not None:
        if exclude.startswith('/') and exclude.endswith('/'):
            exclude_re = re.compile(exclude[1:-1])
            accounts = [acc for acc in accounts if not exclude_re.search(acc.name)]
        else:
            accounts = [acc for acc in accounts if exclude not in acc.name]

    # TODO: This should move to BuchfinkDB.get_accounts()
    if account_type is not None:
        accounts = [acc for acc in accounts if account_type in acc.account_type]

    logger.info(
        'Collected %d account(s): %s', len(accounts), ', '.join([acc.name for acc in accounts])
    )

    return accounts


def with_buchfink_db(func):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        buchfink_db = BuchfinkDB(ctx.obj['BUCHFINK_CONFIG'])
        try:
            ctx.invoke(func, buchfink_db, *args, **kwargs)
        finally:
            # Explicitly close connections
            buchfink_db.__del__()  # pylint: disable=unnecessary-dunder-call

    return update_wrapper(new_func, func)


@click.group()
@click.option('--log-level', '-l', type=str, default='INFO')
@click.option('--config', help='Buchfink config file', envvar='BUCHFINK_CONFIG')
@click.pass_context
def buchfink(ctx, log_level, config):
    ctx.ensure_object(dict)
    ctx.obj['BUCHFINK_CONFIG'] = config or './buchfink.yaml'
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
        click.echo(
            click.style(
                f'Already initialized (buchfink.yaml exists in {bf_dir}), aborting.', fg='red'
            )
        )
        sys.exit(1)

    for init_file in init_data.iterdir():
        logger.debug('Copying %s', init_file.name)
        shutil.copyfile(init_file, bf_dir / init_file.name)

    buchfink_db = BuchfinkDB(target_config)

    click.echo(
        click.style(
            'Successfully initialized in {0}.'.format(buchfink_db.data_directory.absolute()),
            fg='green',
        )
    )

    # Explicitly close connections
    buchfink_db.__del__()  # pylint: disable=unnecessary-dunder-call


@buchfink.command('list')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@click.option('--output', '-o', type=str, default=None, help='Output field')
@with_buchfink_db
def list_(buchfink_db: BuchfinkDB, keyword, account_type, output):
    "List accounts"
    for account in buchfink_db.get_all_accounts():
        if keyword is not None and keyword not in account.name:
            continue

        if account_type is not None and account_type not in account.account_type:
            continue

        if output is None:
            type_and_name = '{0}: {1}'.format(
                account.account_type, click.style(account.name, fg='green')
            )
            address = ' ({0})'.format(account.address) if account.address is not None else ''
            tags = (
                click.style(' {' + ', '.join(account.tags) + '}', fg='blue') if account.tags else ''
            )
            click.echo(type_and_name + address + tags)
        elif output == 'qrcode':
            if account.address:
                qrcode = pyqrcode.create(account.address)
                click.echo(qrcode.terminal(quiet_zone=1))
            else:
                click.echo('Can not create qrcode for {0}'.format(account.name))
        else:
            click.echo('{0}'.format(getattr(account, output)))


@buchfink.command()
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--exclude', '-x', type=str, default=None, help='Exclude by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@click.option('--external', '-e', type=str, multiple=True, help='Use adhoc / external account')
@click.option('--total', is_flag=True, help='Only show totals')
@click.option('--denominate-asset', '-d', type=str, help='Denominate in this asset')
@click.option('--fetch', '-f', is_flag=True, help='Fetch balances from sources')
@click.option(
    '--minimum-balance',
    '-m',
    type=float,
    default=0.0,
    help='Hide balances smaller than this amount (default 0)',
)
@with_buchfink_db
def balances(
    buchfink_db: BuchfinkDB,
    keyword,
    minimum_balance,
    fetch,
    total,
    account_type,
    exclude,
    external,
    denominate_asset,
):
    "Show balances across all accounts"

    assets_sum = {}  # type: Dict[Asset, FVal]
    assets_usd_sum = {}  # type: Dict[Asset, FVal]
    liabilities_sum = {}  # type: Dict[Asset, FVal]
    liabilities_usd_sum = {}  # type: Dict[Asset, FVal]

    buchfink_db.perform_assets_updates()

    accounts = _get_accounts(
        buchfink_db, external=external, keyword=keyword, exclude=exclude, account_type=account_type
    )

    for account in track(accounts, 'Fetching balances'):
        if fetch:
            buchfink_db.fetch_balances(account)

        sheet = buchfink_db.get_balances(account)
        print(f'Balances for {account.name}:', sheet)

        for asset, balance in sheet.assets.items():
            amount = balance.amount
            assets_sum[asset] = assets_sum.get(asset, FVal(0)) + amount
            assets_usd_sum[asset] = assets_usd_sum.get(asset, FVal(0)) + balance.usd_value

        for liability, balance in sheet.liabilities.items():
            amount = balance.amount
            liabilities_sum[liability] = liabilities_sum.get(liability, FVal(0)) + amount
            liabilities_usd_sum[liability] = (
                liabilities_usd_sum.get(liability, FVal(0)) + balance.usd_value
            )

    if denominate_asset is not None:
        currency = buchfink_db.get_asset_by_symbol(denominate_asset)
    else:
        currency = buchfink_db.get_main_currency()

    currency_in_usd = FVal(buchfink_db.inquirer.find_usd_price(currency))
    logger.debug('Denominating in %s (= %s USD)', currency, currency_in_usd)
    table = []
    assets = [obj[0] for obj in sorted(assets_usd_sum.items(), key=itemgetter(1), reverse=True)]
    balance_in_currency_sum = 0
    small_balances_sum = 0

    for asset in assets:
        balance = assets_sum[asset]
        balance_in_currency = FVal(assets_usd_sum.get(asset, 0)) / currency_in_usd
        if balance > ZERO:
            if balance_in_currency > FVal(minimum_balance):
                table.append(
                    [asset.name, balance, asset.symbol, round(float(balance_in_currency), 2)]
                )
            else:
                small_balances_sum += balance_in_currency
            balance_in_currency_sum += balance_in_currency

    if total:
        print(f'Total assets: {round(float(balance_in_currency_sum), 2)} {currency.symbol}')

    else:
        if small_balances_sum > 0:
            table.append(['Others', None, None, round(float(small_balances_sum), 2)])

        table.append(['Total', None, None, round(float(balance_in_currency_sum), 2)])
        print(
            tabulate(table, headers=['Asset', 'Amount', 'Symbol', 'Value (%s)' % currency.symbol])
        )

    if liabilities_sum:
        table = []
        balance_in_currency_sum = 0
        small_balances_sum = 0
        assets = [
            obj[0] for obj in sorted(liabilities_usd_sum.items(), key=itemgetter(1), reverse=True)
        ]
        for asset in assets:
            balance = liabilities_sum[asset]
            balance_in_currency = liabilities_usd_sum.get(asset, FVal(0)) / currency_in_usd
            if balance > ZERO and balance_in_currency >= FVal(minimum_balance):
                balance_in_currency_sum += balance_in_currency
                table.append(
                    [asset.name, balance, asset.symbol, round(float(balance_in_currency), 2)]
                )
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
            print(
                tabulate(
                    table, headers=['Liability', 'Amount', 'Symbol', 'Value (%s)' % currency.symbol]
                )
            )


@buchfink.command('fetch')
@click.option('--external', '-e', type=str, multiple=True, help='Use adhoc / external account')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--exclude', '-x', type=str, default=None, help='Exclude by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@click.option('--actions', 'fetch_actions_', is_flag=True, help='Fetch actions only')
@click.option('--balances', 'fetch_balances', is_flag=True, help='Fetch balances only')
@click.option('--nfts', 'fetch_nfts', is_flag=True, help='Fetch NFT balances only')
@click.option('--trades', 'fetch_trades_', is_flag=True, help='Fetch trades only')
@click.option('--progress/--no-progress', default=True, help='Show progress bar')
@click.option('--full', is_flag=True, help='Fetch everything regardless of last fetch time')
@with_buchfink_db
def fetch_(
    buchfink_db: BuchfinkDB,
    keyword,
    account_type,
    fetch_actions_,
    exclude,
    fetch_balances,
    fetch_trades_,
    fetch_nfts,
    external,
    progress,
    full,
):
    "Fetch events and balances"

    buchfink_db.perform_assets_updates()
    fetch_limited = fetch_actions_ or fetch_balances or fetch_trades_ or fetch_nfts
    error_occured = False

    accounts = _get_accounts(
        buchfink_db, external=external, keyword=keyword, exclude=exclude, account_type=account_type
    )

    for account in track(accounts, description='Fetching data', disable=not progress):
        name = account.name
        fetch_config = account.config.fetch or FetchConfig()

        fetch_actions_for_this_account = (
            not fetch_limited or fetch_actions_
        ) and fetch_config.actions

        fetch_balances_for_this_account = (
            not fetch_limited or fetch_balances
        ) and fetch_config.balances

        fetch_trades_for_this_account = (not fetch_limited or fetch_trades_) and fetch_config.trades

        fetch_nfts_for_this_account = (not fetch_limited or fetch_nfts) and fetch_config.trades

        if fetch_actions_for_this_account:
            try:
                fetch_actions(buchfink_db, account, ignore_fetch_timestamp=full)
            except (IOError, CannotHandleRequest, WrongAssetType):
                logger.exception('Exception during fetch_actions for %s', name)
                error_occured = True

        if fetch_trades_for_this_account:
            try:
                fetch_trades(buchfink_db, account, ignore_fetch_timestamp=full)
            except (IOError, CannotHandleRequest, WrongAssetType):
                logger.exception('Exception during fetch_trades for %s', name)
                error_occured = True

        if fetch_balances_for_this_account:
            try:
                buchfink_db.fetch_balances(account)
            except (IOError, CannotHandleRequest, WrongAssetType):
                logger.exception('Exception during fetch_balances for %s', name)
                error_occured = True
            logger.info('Fetched balances from %s', name)

        if fetch_nfts_for_this_account:
            try:
                nfts = buchfink_db.query_nfts(account)
                if nfts:
                    try:
                        with open(
                            buchfink_db.balances_directory / (name + '.yaml'), 'r'
                        ) as yaml_file:
                            contents = yaml.load(yaml_file, Loader=yaml.SafeLoader)
                            if contents is None:
                                contents = {}
                    except FileNotFoundError:
                        contents = {}

                    with open(buchfink_db.balances_directory / (name + '.yaml'), 'w') as yaml_file:
                        contents['nfts'] = serialize_nfts(nfts)
                        yaml.dump(contents, stream=yaml_file, sort_keys=False, width=-1)

            except (IOError, CannotHandleRequest, RemoteError):
                logger.exception('Exception during query_nfts')
                error_occured = True

    if error_occured:
        print('One or more errors occured')
        # TODO: RETURN exit code 1 on error


@buchfink.command()
@click.option('--external', '-e', type=str, multiple=True, help='Use adhoc / external account')
@click.option('--name', '-n', type=str, required=True)
@click.option('--from', '-f', 'from_date', type=str, required=True)
@click.option('--to', '-t', 'to_date', type=str, required=True)
@with_buchfink_db
def run(buchfink_db: BuchfinkDB, name, from_date, to_date, external):
    "Run a full fetch + report cycle"

    buchfink_db.perform_assets_updates()
    buchfink_db.sync_manual_prices()

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = _get_accounts(buchfink_db)

    result = run_report(
        buchfink_db,
        accounts,
        ReportConfig(
            name=name,
            from_dt=datetime.fromisoformat(from_date),
            to_dt=datetime.fromisoformat(to_date),
        ),
    )

    logger.info('Overview: %s', result['overview'])


@buchfink.command('asset')
@click.argument('identifier', type=str)
@with_buchfink_db
def asset_(buchfink_db: BuchfinkDB, identifier: str):
    "Asset info"
    direct_hit = None
    try:
        direct_hit = deserialize_asset(identifier)
    except ValueError:
        pass
    assets = buchfink_db.globaldb.get_assets_with_symbol(identifier)

    # Make sure that direct hit is in list and is first
    if direct_hit is not None:
        if direct_hit in assets:
            assets.remove(direct_hit)
        assets.insert(0, direct_hit)

    table = []
    for asset in assets:
        table.append(
            [
                '*' if asset == direct_hit else '',
                str(asset.name),
                str(asset.symbol),
                str(asset.asset_type),
                str(asset.identifier),
                str(asset.chain_id) if asset.asset_type == AssetType.EVM_TOKEN else '',
            ]
        )

    print(tabulate(table, headers=['Hit', 'Name', 'Symbol', 'Type', 'Identifier', 'Chain']))


@buchfink.command('format')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--type', '-t', 'account_type', type=str, default=None, help='Filter by account type')
@with_buchfink_db
def format_(buchfink_db: BuchfinkDB, keyword: Optional[str], account_type: Optional[str]):
    "Reads and formats all balances, trades and actions"
    # TODO: nfts are currently not reformatted

    accounts = _get_accounts(buchfink_db, keyword=keyword, account_type=account_type)

    for account in accounts:
        name = account.name
        logger.info('Formatting %s', name)

        actions_path = buchfink_db.actions_directory / (name + '.yaml')
        if os.path.exists(actions_path):
            actions = buchfink_db.get_actions_from_file(actions_path)
            write_actions(buchfink_db, account, actions)

        trades_path = buchfink_db.trades_directory / (name + '.yaml')
        if os.path.exists(trades_path):
            trades = buchfink_db.get_trades_from_file(trades_path)
            write_trades(buchfink_db, account, trades)

        balances_path = buchfink_db.balances_directory / (name + '.yaml')
        if os.path.exists(balances_path):
            balances_ = buchfink_db.get_balances_from_file(balances_path)
            buchfink_db.write_balances(account, balances_)


@buchfink.command('events')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--asset', '-a', type=str, default=None, help='Filter by asset')
@with_buchfink_db
def events_(buchfink_db: BuchfinkDB, keyword, asset):
    "List events"

    events: List[Tuple[Union[HistoryBaseEntry, Trade], Account]] = []

    filter_asset = buchfink_db.get_asset_by_symbol(asset) if asset is not None else None
    accounts = _get_accounts(buchfink_db, keyword=keyword)

    for account in accounts:
        events.extend(
            (trade, account)
            for trade in buchfink_db.get_local_trades_for_account(account.name)
            if filter_asset is None or filter_asset in (trade.base_asset, trade.quote_asset)
        )

        events.extend(
            (event, account)
            for event in buchfink_db.get_local_ledger_actions_for_account(account.name)
            if filter_asset is None or filter_asset in (event.asset,)
        )

    def get_timestamp(event) -> Timestamp:
        if isinstance(event, HistoryBaseEntry):
            return ts_ms_to_sec(event.timestamp)
        return event.timestamp

    events = sorted(events, key=lambda ev_acc: get_timestamp(ev_acc[0]))

    if events:
        table = []
        for event, account in events:
            # try:
            #     asset_currency = historian.query_historical_price(
            #         from_asset=action.asset, to_asset=currency, timestamp=action.timestamp
            #     )
            # except NoPriceForGivenTimestamp:
            #     asset_currency = FVal('0.0')

            if isinstance(event, Trade):
                trade: Trade = event
                table.append(
                    [
                        serialize_timestamp(trade.timestamp),
                        str(trade.trade_type),
                        serialize_decimal(trade.amount.num),
                        str(trade.base_asset.symbol),
                        serialize_decimal((trade.amount * trade.rate).num),
                        str(trade.quote_asset.symbol),
                        serialize_decimal(trade.rate.num),
                        str(account.name),
                    ]
                )
            elif isinstance(event, HistoryEvent):
                table.append(
                    [
                        serialize_timestamp(ts_ms_to_sec(event.timestamp)),
                        str(event.event_subtype),
                        str(event.balance.amount.num),
                        str(event.asset.symbol_or_name()),
                        '',
                        '',
                        str(''),
                        str(account.name),
                    ]
                )
            elif isinstance(event, HistoryBaseEntry):
                print(event.timestamp)
                table.append(
                    [
                        serialize_timestamp(ts_ms_to_sec(event.timestamp)),
                        str(event.event_subtype),
                        serialize_decimal(event.balance.amount.num),
                        str(event.asset.symbol_or_name()),
                        serialize_decimal(event.balance.amount.num),
                        str(event.asset.symbol_or_name()),
                        str(''),
                        str(account.name),
                    ]
                )
            else:
                raise RuntimeError('Unknown event type')
        print(
            tabulate(
                table,
                headers=[
                    'Time',
                    'Type',
                    'Amount',
                    'Quote Asset',
                    'Amount',
                    'Base Asset',
                    'Rate',
                    'Account',
                ],
            )
        )


@buchfink.command('report')
@click.option('--external', '-e', type=str, multiple=True, help='Use adhoc / external account')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@click.option('--report', type=str, default=None, help='Filter by keyword in report name')
@click.option('--asset', '-a', type=str, default=None, help='Filter by asset')
@click.option(
    '--render-only',
    is_flag=True,
    help='Do not actually run the report but only render the template',
)
@click.option(
    '--year', type=int, default=None, help='Run adhoc-report for given year', multiple=True
)
@click.option('--progress/--no-progress', default=True, help='Show progress bar')
@click.option(
    '--vcs-check/--no-vcs-check', default=True, help='Check if we are in a clean VCS state'
)
@click.option('--template', type=str, default=None, help='Render using this template')
@with_buchfink_db
def report_(
    buchfink_db: BuchfinkDB,
    keyword,
    external,
    report,
    asset,
    year,
    template,
    render_only,
    progress: bool,
    vcs_check: bool,
):
    "Generate reports for all active report configs and output overview table"

    limit_assets = [buchfink_db.get_asset_by_symbol(asset)] if asset is not None else None

    if not render_only:
        buchfink_db.perform_assets_updates()
        buchfink_db.sync_manual_prices()

    if vcs_check:
        # Check wether we have uncommited changes
        # Currently only implemented for git
        try:
            # Check for uncommited changes
            subprocess.check_output(['git', 'diff', '--quiet'], cwd=buchfink_db.data_directory)
            # Check for staged changes
            subprocess.check_output(
                ['git', 'diff', '--cached', '--quiet'], cwd=buchfink_db.data_directory
            )
        except subprocess.CalledProcessError:
            logger.error(
                'You have uncommited or staged changes. Please commit or '
                'stash them before running a report, or use --no-vcs-check'
            )
            sys.exit(1)

    results = {}

    if external:
        accounts = [account_from_string(ext, buchfink_db) for ext in external]
    else:
        accounts = _get_accounts(buchfink_db, keyword=keyword)

    if year:
        reports = [
            ReportConfig(
                name=f'adhoc-{_year}',
                title=str(_year),
                template=template,
                from_dt=datetime(_year, 1, 1),
                to_dt=datetime(_year + 1, 1, 1),
            )
            for _year in year
        ]
    else:
        reports = [
            report_
            for report_ in buchfink_db.get_all_reports()
            if (report is None or report in report_.name) and report_.active
        ]

    logger.info(
        'Running %s report%s: %s',
        len(reports),
        's' if len(reports) != 1 else '',
        ', '.join([report_.name for report_ in reports]),
    )

    for _report in track(reports, description='Generating reports', disable=not progress):
        name = str(_report.name)
        if not render_only:
            results[name] = run_report(buchfink_db, accounts, _report, limit_assets=limit_assets)
        if _report.template:
            render_report(buchfink_db, _report)

    if results:
        table = []
        for report_name, result in results.items():
            table.append(
                [report_name, result['pnl_totals']['free'], result['pnl_totals']['taxable']]
            )
        print(tabulate(table, headers=['Report', 'Free P/L', 'Taxable P/L']))


@buchfink.command()
@with_buchfink_db
def allowances(buchfink_db):
    # pylint: disable = W
    "Show the amount of each asset that you could sell tax-free"

    buchfink_db.perform_assets_updates()
    buchfink_db.sync_manual_prices()

    num_matched_accounts = 0
    all_trades = []

    for account in buchfink_db.get_all_accounts():
        num_matched_accounts += 1
        all_trades.extend(buchfink_db.get_local_trades_for_account(account.name))

    logger.info(
        'Collected %d trades from %d exchange account(s)', len(all_trades), num_matched_accounts
    )

    accountant = buchfink_db.get_accountant()
    # currency = buchfink_db.get_main_currency()
    # currency_in_usd = FVal(buchfink_db.inquirer.find_usd_price(currency))
    epoch_start_ts = Timestamp(0)
    epoch_end_ts = ts_now()

    accountant.process_history(epoch_start_ts, epoch_end_ts, all_trades, [], [], [], [], [])
    # total_usd = FVal(0)
    # table = []

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
@with_buchfink_db
def quote(
    buchfink_db: BuchfinkDB,
    asset: Tuple[str],
    amount: float,
    base_asset_: Optional[str],
    timestamp: Optional[str],
):
    """
    Show a price quote. In addition to the options flags, the following short syntax
    is also supported:

        buchfink quote 100 ETH

        buchfink quote ETH/BTC

        buchfink quote 2.5 ETH/BTC
    """
    buchfink_db.perform_assets_updates()
    buchfink_db.sync_manual_prices()

    base_asset = (
        buchfink_db.get_asset_by_symbol(base_asset_)
        if base_asset_
        else buchfink_db.get_main_currency()
    )
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
        if '/' in symbol and '[' not in symbol:  # TODO support "A[eip155:1/id]/B" syntax
            symbol, base_symbol = symbol.split('/')
            base_asset = buchfink_db.get_asset_by_symbol(base_symbol)
            base_in_usd = FVal(buchfink_db.inquirer.find_usd_price(base_asset))
        quote_asset = buchfink_db.get_asset_by_symbol(symbol)
        if ds_timestamp:
            asset_usd = historian.query_historical_price(
                from_asset=quote_asset, to_asset=a_usd, timestamp=ds_timestamp
            )
        else:
            asset_usd = FVal(buchfink_db.inquirer.find_usd_price(quote_asset))
        click.echo(
            '{} {} ({}) = {} {}'.format(
                click.style(f'{amount}', fg='white'),
                click.style(quote_asset.symbol, fg='green'),
                click.style(quote_asset.name, fg='white'),
                click.style(f'{FVal(amount) * asset_usd / base_in_usd}', fg='white'),
                click.style(base_asset.symbol, fg='green'),
            )
        )


@buchfink.command('cache')
@click.argument('asset', nargs=-1)
@click.option('--base-asset', '-b', 'base_asset_', type=str, default=None)
@with_buchfink_db
def cache(buchfink_db: BuchfinkDB, asset: Tuple[str], base_asset_: Optional[str]):
    """
    Build a historical price cache
    """
    base_asset = (
        buchfink_db.get_asset_by_symbol(base_asset_)
        if base_asset_
        else buchfink_db.get_main_currency()
    )

    for symbol in asset:
        asset_2 = buchfink_db.get_asset_by_symbol(symbol)
        buchfink_db.cryptocompare.create_cache(asset_2, base_asset, False)


@buchfink.command('explore')
@click.option('--external', '-e', type=str, multiple=True, help='Use adhoc / external account')
@click.option('--keyword', '-k', type=str, default=None, help='Filter by keyword in account name')
@with_buchfink_db
def explore(buchfink_db: BuchfinkDB, keyword, external):
    "Show block explorer for account"

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
        'Collected %d account(s): %s', len(accounts), ', '.join([acc.name for acc in accounts])
    )

    if len(accounts) == 0:
        click.echo(click.style('No accounts selected', fg='red'))
        sys.exit(1)
    elif len(accounts) > 1:
        click.echo(click.style('More than one account selected', fg='red'))
        sys.exit(1)
    else:
        account = accounts[0]

        if account.account_type == 'ethereum':
            webbrowser.open('https://etherscan.io/address/{0}'.format(account.address))


@buchfink.command('historical-prices')
def historical_prices(buchfink_db: BuchfinkDB):
    "Show historical prices for an asset"

    for asset in buchfink_db.globaldb.get_historical_price_range():
        if asset.asset_type == AssetType.EVM_TOKEN:
            continue

        print(asset.symbol)
        print('------------------')
        for price in buchfink_db.globaldb.get_historical_prices(asset):
            print(price.timestamp, price.price)

        print()


if __name__ == '__main__':
    buchfink(obj={})  # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
