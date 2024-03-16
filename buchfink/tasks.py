import logging
import os.path
from typing import List, Optional, Tuple

import pydantic
import yaml
from rotkehlchen.utils.misc import ts_now
from web3.exceptions import CannotHandleRequest

from buchfink.serialization import deserialize_timestamp, serialize_timestamp

from .classification import classify_tx
from .datatypes import (
    EvmEvent,
    HistoryBaseEntry,
    HistoryEventSubType,
    HistoryEventType,
    Timestamp,
    Trade,
)
from .db import BuchfinkDB
from .models import Account
from .serialization import serialize_events, serialize_trades


class ActionsMetadata(pydantic.BaseModel):
    fetch_timestamp: Timestamp


class TradesMetadata(pydantic.BaseModel):
    fetch_timestamp: Timestamp


logger = logging.getLogger(__name__)


def _get_trades_metadata(buchfink_db: BuchfinkDB, account: Account) -> Optional[TradesMetadata]:
    trades_path = buchfink_db.trades_directory / (account.name + '.yaml')
    if os.path.exists(trades_path):
        with open(trades_path, 'r') as yaml_file:
            contents = yaml.safe_load(yaml_file)
            if 'metadata' in contents and 'fetch_timestamp' in contents['metadata']:
                return TradesMetadata(
                    fetch_timestamp=deserialize_timestamp(contents['metadata']['fetch_timestamp'])
                )
    return None


def write_trades(
    buchfink_db: BuchfinkDB,
    account: Account,
    trades: List[Trade],
    metadata: Optional[TradesMetadata] = None,
):
    trades_path = buchfink_db.trades_directory / (account.name + '.yaml')
    if not trades and not metadata:
        if os.path.exists(trades_path):
            os.unlink(trades_path)
        return
    with open(trades_path, 'w') as yaml_file:
        contents: dict = {'trades': serialize_trades(trades)}
        if metadata:
            contents['metadata'] = {
                'fetch_timestamp': serialize_timestamp(metadata.fetch_timestamp)
            }
        yaml.dump(
            contents,
            stream=yaml_file,
            sort_keys=False,
            width=-1,
        )


def _get_actions_metadata(buchfink_db: BuchfinkDB, account: Account) -> Optional[ActionsMetadata]:
    actions_path = buchfink_db.actions_directory / (account.name + '.yaml')
    if os.path.exists(actions_path):
        with open(actions_path, 'r') as yaml_file:
            contents = yaml.safe_load(yaml_file)
            if 'metadata' in contents and 'fetch_timestamp' in contents['metadata']:
                return ActionsMetadata(
                    fetch_timestamp=deserialize_timestamp(contents['metadata']['fetch_timestamp'])
                )
    return None


def write_actions(
    buchfink_db: BuchfinkDB,
    account: Account,
    actions: List[HistoryBaseEntry],
    metadata: Optional[ActionsMetadata] = None,
):
    actions_path = buchfink_db.actions_directory / (account.name + '.yaml')
    if not actions and not metadata:
        if os.path.exists(actions_path):
            os.unlink(actions_path)
        return

    with open(actions_path, 'w') as yaml_file:
        contents: dict = {'actions': serialize_events(actions)}
        if metadata:
            contents['metadata'] = {
                'fetch_timestamp': serialize_timestamp(metadata.fetch_timestamp)
            }

        yaml.dump(
            contents,
            stream=yaml_file,
            sort_keys=False,
            width=-1,
        )


def fetch_actions(buchfink_db: BuchfinkDB, account: Account, ignore_fetch_timestamp: bool = False):
    name = account.name
    actions = []
    existing_actions = []

    now = ts_now()
    start_ts = Timestamp(0)
    metadata = _get_actions_metadata(buchfink_db, account)

    if metadata and metadata.fetch_timestamp and not ignore_fetch_timestamp:
        existing_actions = buchfink_db.get_actions_from_file(
            buchfink_db.actions_directory / (name + '.yaml')
        )
        actions.extend(existing_actions)
        start_ts = metadata.fetch_timestamp

    if account.account_type == 'ethereum':
        logger.info('Analyzing ethereum transactions for %s', name)

        txs_and_receipts = buchfink_db.get_eth_transactions(
            account, with_receipts=True, start_ts=start_ts, end_ts=now
        )

        for txn, receipt in txs_and_receipts:
            if receipt is None:
                raise ValueError('Could not get receipt')

            additional_actions = classify_tx(account, txn, receipt)
            for act in additional_actions:
                logger.debug('Found action: %s', act)
            actions.extend(additional_actions)

        for tx_tuple in txs_and_receipts:
            tx, receipt = tx_tuple
            if receipt is None:
                logger.warning('No receipt for %s', tx.tx_hash)
                continue

            # pylint: disable=protected-access
            buchfink_db._active_eth_address = account.address
            buchfink_db.evm_tx_decoder.base.tracked_accounts = buchfink_db.get_blockchain_accounts()
            try:
                ev: Tuple[List[EvmEvent], bool] = (
                    buchfink_db.evm_tx_decoder._get_or_decode_transaction_events(
                        tx, receipt, ignore_cache=False
                    )
                )
                events, _ = ev

            except (IOError, CannotHandleRequest) as e:
                logger.warning('Exception while decoding events for tx %s: %s', tx.tx_hash.hex(), e)
                continue

            for event in events:
                if event.event_subtype == HistoryEventSubType.FEE and event.counterparty == 'gas':
                    actions.append(event)
                elif event.event_subtype == HistoryEventSubType.APPROVE:
                    pass
                elif event.event_type == HistoryEventType.TRADE:
                    if event.asset.is_nft() or 'eip155:1/erc721:' in event.asset.identifier:
                        # For now we will ignore NFT events
                        continue
                    actions.append(event)
                else:
                    logger.warning(
                        'Ignoring event %s (summary=%s, event_identifier=0x%s, '
                        'sequence_index=%s)',
                        event.event_type,
                        event,
                        event.event_identifier,
                        event.sequence_index,
                    )

            buchfink_db._active_eth_address = None

    elif account.account_type == 'exchange':
        logger.info('Fetching exhange actions for %s', name)

        exchange = buchfink_db.get_exchange(name)

        api_key_is_valid, error = exchange.validate_api_key()

        if not api_key_is_valid:
            logger.critical(
                'Skipping exchange %s because API key is not valid (%s)',
                account.name,
                error,
            )

        else:
            logger.info('Fetching actions for %s (start_ts=%s, end_ts=%s)', name, start_ts, now)

            exchange.query_online_income_loss_expense(start_ts=start_ts, end_ts=now)

            fetched_actions = exchange.query_income_loss_expense(
                start_ts=start_ts, end_ts=now, only_cache=True
            )

            actions.extend(fetched_actions)

    elif account.account_type == 'generic':
        pass

    else:
        logger.debug('No way to retrieve actions for %s, yet', name)

    annotated_actions = []
    if not existing_actions:
        # We would need to respect timestamps here...
        annotations_path = buchfink_db.annotations_directory / (name + '.yaml')

        if os.path.exists(annotations_path):
            annotated_actions = buchfink_db.get_actions_from_file(
                annotations_path, include_trades=False
            )

        actions.extend(annotated_actions)

    logger.info(
        'Fetched %d action(s) (%d existing, %d annotated) from %s',
        len(actions),
        len(existing_actions),
        len(annotated_actions),
        name,
    )

    write_actions(buchfink_db, account, actions, metadata=ActionsMetadata(fetch_timestamp=now))


def fetch_trades(buchfink_db: BuchfinkDB, account: Account, ignore_fetch_timestamp: bool = False):
    trades: List[Trade] = []
    existing_trades: List[Trade] = []
    annotated: List[Trade] = []
    name = account.name

    start_ts = Timestamp(0)
    now = ts_now()
    metadata = _get_trades_metadata(buchfink_db, account)

    if metadata and metadata.fetch_timestamp and not ignore_fetch_timestamp:
        existing_trades = buchfink_db.get_trades_from_file(
            buchfink_db.trades_directory / (name + '.yaml')
        )
        trades.extend(existing_trades)
        start_ts = metadata.fetch_timestamp

    if account.account_type == 'exchange':
        logger.info('Fetching exhange trades for %s', name)

        exchange = buchfink_db.get_exchange(name)

        api_key_is_valid, error = exchange.validate_api_key()

        if not api_key_is_valid:
            logger.critical(
                'Skipping exchange %s because API key is not valid (%s)',
                account.name,
                error,
            )

        else:
            logger.info('Fetching trades for %s (start_ts=%s, end_ts=%s)', name, start_ts, now)

            exchange.query_online_trade_history(start_ts=start_ts, end_ts=now)

            fetched_trades = exchange.query_trade_history(
                start_ts=start_ts, end_ts=now, only_cache=True
            )

            trades.extend(fetched_trades)

    annotations_path = buchfink_db.annotations_directory / (name + '.yaml')

    if not existing_trades:
        if os.path.exists(annotations_path):
            annotated = buchfink_db.get_trades_from_file(annotations_path)

    trades.extend(annotated)

    logger.info(
        'Fetched %d trades(s) (%d existing, %d annotated) from %s',
        len(trades),
        len(existing_trades),
        len(annotated),
        name,
    )

    existing = set()
    unique_trades = []
    for trade in trades:
        if (trade.location, trade.link) not in existing:
            existing.add((trade.location, trade.link))
            unique_trades.append(trade)
        else:
            logger.warning('Removing duplicate trade: %s', trade)

    write_trades(buchfink_db, account, unique_trades, metadata=TradesMetadata(fetch_timestamp=now))
