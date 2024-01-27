import logging
import os.path
from datetime import datetime
from typing import List, Tuple

import yaml
from web3.exceptions import CannotHandleRequest

from .classification import classify_tx
from .datatypes import (
    EvmEvent,
    # HistoryEvent,
    HistoryBaseEntry,
    HistoryEventSubType,
    HistoryEventType,
    Timestamp,
    Trade,
)
from .db import BuchfinkDB
from .models import Account
from .serialization import serialize_events, serialize_trades

# TOOD
epoch_start_ts = Timestamp(int(datetime(2011, 1, 1).timestamp()))
epoch_end_ts = Timestamp(int(datetime(2031, 1, 1).timestamp()))

logger = logging.getLogger(__name__)


def write_trades(buchfink_db: BuchfinkDB, account: Account, trades: List[Trade]):
    trades_path = buchfink_db.trades_directory / (account.name + '.yaml')
    if not trades:
        if os.path.exists(trades_path):
            os.unlink(trades_path)
        return
    with open(trades_path, 'w') as yaml_file:
        yaml.dump(
            {'trades': serialize_trades(trades)},
            stream=yaml_file,
            sort_keys=False,
            width=-1,
        )


def write_actions(buchfink_db: BuchfinkDB, account: Account, actions: List[HistoryBaseEntry]):
    actions_path = buchfink_db.actions_directory / (account.name + '.yaml')
    if not actions:
        if os.path.exists(actions_path):
            os.unlink(actions_path)
        return
    with open(actions_path, 'w') as yaml_file:
        yaml.dump(
            {'actions': serialize_events(actions)},
            stream=yaml_file,
            sort_keys=False,
            width=-1,
        )


def fetch_actions(buchfink_db: BuchfinkDB, account: Account):
    name = account.name
    actions = []

    if account.account_type == 'ethereum':
        logger.info('Analyzing ethereum transactions for %s', name)
        txs_and_receipts = buchfink_db.get_eth_transactions(account, with_receipts=True)

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
                ev: Tuple[
                    List[EvmEvent], bool
                ] = buchfink_db.evm_tx_decoder._get_or_decode_transaction_events(
                    tx, receipt, ignore_cache=False
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
        pass

    elif account.account_type == 'generic':
        pass

    else:
        logger.debug('No way to retrieve actions for %s, yet', name)

    annotations_path = buchfink_db.annotations_directory / (name + '.yaml')

    if os.path.exists(annotations_path):
        annotated = buchfink_db.get_actions_from_file(annotations_path, include_trades=False)
    else:
        annotated = []

    logger.info(
        'Fetched %d action(s) (%d annotated) from %s',
        len(actions) + len(annotated),
        len(annotated),
        name,
    )

    actions.extend(annotated)

    write_actions(buchfink_db, account, actions)


def fetch_trades(buchfink_db: BuchfinkDB, account: Account):
    trades: List[Trade] = []
    name = account.name

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
            trades, _ = exchange.query_online_trade_history(
                start_ts=epoch_start_ts, end_ts=epoch_end_ts
            )
    annotations_path = buchfink_db.annotations_directory / (name + '.yaml')

    if os.path.exists(annotations_path):
        annotated = buchfink_db.get_trades_from_file(annotations_path)
    else:
        annotated = []

    logger.info(
        'Fetched %d trades(s) (%d annotated) from %s',
        len(trades) + len(annotated),
        len(annotated),
        name,
    )

    trades.extend(annotated)

    existing = set()
    unique_trades = []
    for trade in trades:
        if (trade.location, trade.link) not in existing:
            existing.add((trade.location, trade.link))
            unique_trades.append(trade)
        else:
            logger.warning('Removing duplicate trade: %s', trade)

    write_trades(buchfink_db, account, unique_trades)
