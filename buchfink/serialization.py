import re
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import reduce
import operator
from operator import itemgetter
from typing import Any, Dict, List, Tuple

from rotkehlchen.accounting.types import MissingPrice
from rotkehlchen.assets.utils import symbol_to_asset_or_token
from rotkehlchen.constants import ZERO
from rotkehlchen.constants.resolver import ChainID
from rotkehlchen.serialization.deserialize import deserialize_evm_address
from rotkehlchen.history.events.structures.swap import SwapEvent, create_swap_events
from rotkehlchen.types import AssetAmount, TokenKind, Location, deserialize_evm_tx_hash
from rotkehlchen.utils.misc import ts_ms_to_sec

from buchfink.datatypes import (
    Asset,
    AssetMovement,
    Balance,
    BalanceSheet,
    EvmEvent,
    EvmToken,
    FVal,
    HistoryBaseEntry,
    HistoryEvent,
    HistoryEventSubType,
    HistoryEventType,
    Nfts,
    Timestamp,
    TimestampMS,
    EventDirection,
)
from buchfink.exceptions import UnknownAsset
from buchfink.models.config import AssetConfig


logger = logging.getLogger(__name__)


def serialize_timestamp(timestamp: Timestamp) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def serialize_timestamp_ms(timestamp_ms: TimestampMS) -> str:
    return datetime.fromtimestamp(ts_ms_to_sec(timestamp_ms), tz=timezone.utc).isoformat()


def deserialize_timestamp(timestamp: str) -> Timestamp:
    "Converts ISO date or a UNIX timestamp to a Timestamp"
    if timestamp.endswith('Z'):
        timestamp = timestamp[:-1]
    try:
        return int(datetime.fromisoformat(timestamp).timestamp())
    except ValueError:
        return int(timestamp)


def deserialize_timestamp_ms(timestamp: str) -> Timestamp:
    return deserialize_timestamp(timestamp) * 1000


def deserialize_ledger_action(action_dict) -> HistoryEvent:
    # TODO: incorporate "link" into HistoryEvent

    if 'link' in action_dict and action_dict['link'] in ('', None, 'None', 'null'):
        del action_dict['link']

    if 'income' in action_dict:
        amount, asset = deserialize_amount(action_dict['income'])
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.EXTERNAL,
            event_type=HistoryEventType.RECEIVE,
            event_subtype=HistoryEventSubType.REWARD,
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    if 'airdrop' in action_dict:
        amount, asset = deserialize_amount(action_dict['airdrop'])
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.EXTERNAL,
            event_type=HistoryEventType.RECEIVE,
            event_subtype=HistoryEventSubType.AIRDROP,
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    if 'loss' in action_dict:
        amount, asset = deserialize_amount(action_dict['loss'])
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.EXTERNAL,
            event_type=HistoryEventType.LOSS,
            event_subtype=HistoryEventSubType.LIQUIDATE,
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    if 'gift' in action_dict:
        amount, asset = deserialize_amount(action_dict['gift'])
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.EXTERNAL,
            event_type=HistoryEventType.RECEIVE,
            event_subtype=HistoryEventSubType.NONE,
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    if 'spend' in action_dict:
        amount, asset = deserialize_amount(action_dict['spend'])
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.EXTERNAL,
            event_type=HistoryEventType.SPEND,
            event_subtype=HistoryEventSubType.NONE,
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    if 'event_type' in action_dict and 'asset' in action_dict:
        amount, asset = deserialize_amount(f'{action_dict["amount"]} {action_dict["asset"]}')
        return HistoryEvent(
            group_identifier=action_dict.get('group_identifier', str(action_dict.get('link', ''))),
            sequence_index=action_dict.get('sequence_index', 0),
            timestamp=deserialize_timestamp_ms(action_dict['timestamp']),
            location=Location.deserialize(action_dict.get('location') or 'external'),
            event_type=HistoryEventType.deserialize(action_dict['event_type']),
            event_subtype=HistoryEventSubType.deserialize(action_dict.get('event_subtype', 'none')),
            asset=asset,
            amount=amount,
            notes=str(action_dict.get('notes', '') or action_dict.get('user_notes', '')),
        )

    raise ValueError(f'Unable to parse ledger action: {action_dict}')


def deserialize_trade(trade_dict) -> List[SwapEvent]:
    if 'pair' in trade_dict:
        # Legacy format with pair - limited info, create a single spend event
        trade_type = deserialize_tradetype(trade_dict['trade_type'])
        group_id = str(trade_dict.get('link', ''))
        timestamp = TimestampMS(deserialize_timestamp_ms(trade_dict['timestamp']))
        location = Location.deserialize(trade_dict.get('location') or 'external')
        base_asset = deserialize_asset(trade_dict['pair'].split('/')[0])
        amount = deserialize_fval(trade_dict['amount'])
        notes = f'Legacy trade {trade_dict["pair"]}'
        subtype = (
            HistoryEventSubType.SPEND
            if trade_type == EventDirection.OUT
            else HistoryEventSubType.RECEIVE
        )
        return [
            SwapEvent(
                group_identifier=group_id,
                timestamp=timestamp,
                location=location,
                event_subtype=subtype,
                asset=base_asset,
                amount=amount,
                notes=notes,
            )
        ]

    if 'buy' in trade_dict:
        trade_type = EventDirection.IN
        amount, base_asset = deserialize_amount(trade_dict['buy'])
    elif 'sell' in trade_dict:
        trade_type = EventDirection.OUT
        amount, base_asset = deserialize_amount(trade_dict['sell'])
    elif 'trade_receive' in trade_dict:
        recv_amount, recv_asset = deserialize_amount(trade_dict['trade_receive'])
        return [
            SwapEvent(
                group_identifier=str(
                    trade_dict.get('group_identifier', trade_dict.get('link', ''))
                ),
                sequence_index=trade_dict.get('sequence_index', 0),
                timestamp=TimestampMS(deserialize_timestamp_ms(trade_dict['timestamp'])),
                location=Location.deserialize(trade_dict.get('location') or 'external'),
                event_subtype=HistoryEventSubType.RECEIVE,
                asset=recv_asset,
                amount=recv_amount,
                notes=trade_dict.get('user_notes'),
            )
        ]
    elif 'trade_spend' in trade_dict:
        spend_amount, spend_asset = deserialize_amount(trade_dict['trade_spend'])
        return [
            SwapEvent(
                group_identifier=str(
                    trade_dict.get('group_identifier', trade_dict.get('link', ''))
                ),
                sequence_index=trade_dict.get('sequence_index', 0),
                timestamp=TimestampMS(deserialize_timestamp_ms(trade_dict['timestamp'])),
                location=Location.deserialize(trade_dict.get('location') or 'external'),
                event_subtype=HistoryEventSubType.SPEND,
                asset=spend_asset,
                amount=spend_amount,
                notes=trade_dict.get('user_notes'),
            )
        ]
    else:
        raise ValueError('Invalid trade: ' + str(trade_dict))

    quote_amount, quote_asset = deserialize_amount(trade_dict['for'])

    if base_asset is None:
        raise ValueError('No base asset provided')

    if quote_asset is None:
        raise ValueError('No quote asset provided')

    group_id = str(trade_dict.get('link', ''))
    timestamp = TimestampMS(deserialize_timestamp_ms(trade_dict['timestamp']))
    location = Location.deserialize(trade_dict.get('location') or 'external')
    notes = f'Trade {amount} {base_asset} for {quote_amount} {quote_asset}'

    if trade_type == EventDirection.IN:
        # buy: spend quote asset, receive base asset
        spend = AssetAmount(asset=quote_asset, amount=quote_amount)
        receive = AssetAmount(asset=base_asset, amount=amount)
    else:
        # sell: spend base asset, receive quote asset
        spend = AssetAmount(asset=base_asset, amount=amount)
        receive = AssetAmount(asset=quote_asset, amount=quote_amount)

    return create_swap_events(
        timestamp=timestamp,
        location=location,
        spend=spend,
        receive=receive,
        group_identifier=group_id,
        spend_notes=notes,
        receive_notes=notes,
    )


QUANT_DECIMAL = Decimal('0.00000000000001')
RE_IRREGULAR_CHAR = re.compile(r'[^a-zA-Z0-9\-\+]+')


def serialize_decimal(dec: Decimal) -> str:
    "return a non-scientific, non-trailing-zero number representation"
    try:
        ser_amount = str(dec.quantize(QUANT_DECIMAL))
    except InvalidOperation:
        ser_amount = str(dec)
    if 'E' in ser_amount or 'e' in ser_amount:
        ser_amount = '{0:.14f}'.format(float(dec))
    return ser_amount.rstrip('0').rstrip('.')


def serialize_asset(
    asset: Asset,
    allow_name_if_own_chain: bool = True,
    allow_name_if_globally_unique: bool = False,
    allow_name_if_unique_on_eth: bool = False,
) -> str:
    asset_name = asset.symbol_or_name()

    if RE_IRREGULAR_CHAR.search(asset_name):
        # Got irregular characters in the name
        clean_name = RE_IRREGULAR_CHAR.sub('', asset_name)
        return f'{clean_name}[{asset.identifier}]'

    if allow_name_if_own_chain and asset_name == asset.identifier:
        # If the symbol_or_name is the same as the identifier, we can simply
        # return the identifier.
        return asset.identifier

    try:
        if allow_name_if_globally_unique and asset == symbol_to_asset_or_token(asset_name):
            # If we resolve the asset symbol_or_name and receive the same
            # asset, we can simply return the symbol_or_name.
            return asset_name
    except UnknownAsset:
        pass

    try:
        if allow_name_if_unique_on_eth and asset == symbol_to_asset_or_token(
            asset_name, chain_id=ChainID.ETHEREUM
        ):
            return asset_name
    except UnknownAsset:
        pass

    return f'{asset_name}[{asset.identifier}]'


def serialize_amount(amount: FVal, asset: Asset) -> str:
    return '{0} {1}'.format(serialize_decimal(amount.num), serialize_asset(asset))


def serialize_balance(balance: Balance, asset: Asset) -> dict:
    return {'amount': serialize_decimal(balance.amount.num), 'asset': serialize_asset(asset)}


def serialize_balances(balances: BalanceSheet, skip_nfts=True) -> dict:
    def _is_nft(asset):
        return isinstance(asset, EvmToken) and asset.token_kind == TokenKind.ERC721

    def _sum_balances(balance_dict: dict[str, Balance]) -> Balance:
        """Sum all Balance objects across all labels/locations for an asset."""
        assert isinstance(balance_dict, dict), f'Expected dict, got {type(balance_dict)}'
        return reduce(operator.add, balance_dict.values(), Balance())

    ser_balances = {}
    if balances.assets:
        ser_balances['assets'] = sorted(
            [
                serialize_balance(total_bal, asset)
                for asset, bal_dict in balances.assets.items()
                if (total_bal := _sum_balances(bal_dict)).amount.num >= QUANT_DECIMAL
                and (skip_nfts is False or not _is_nft(asset))
            ],
            key=itemgetter('asset'),
        )
    if balances.liabilities:
        ser_balances['liabilities'] = sorted(
            [
                serialize_balance(total_bal, asset)
                for asset, bal_dict in balances.liabilities.items()
                if (total_bal := _sum_balances(bal_dict)).amount > 0
                and (skip_nfts is False or not _is_nft(asset))
            ],
            key=itemgetter('asset'),
        )
    return ser_balances


def deserialize_balance(balance: Dict[str, Any], buchfink_db) -> Tuple[Balance, Asset]:
    amount = FVal(balance['amount'])
    asset = buchfink_db.get_asset_by_symbol(balance['asset'])
    try:
        usd_value = amount * FVal(buchfink_db.inquirer.find_usd_price(asset))
    except (ValueError, TypeError, KeyError) as e:
        usd_value = FVal(0)
        logger.exception('Could not find USD price for %s: %s', asset, e)
    return Balance(amount, usd_value), asset


def deserialize_amount(amount: str) -> Tuple[FVal, Asset]:
    if not isinstance(amount, str):
        raise ValueError(f'Expected str, got {type(amount)}: {amount}')

    elems = amount.split(' ')
    fval = FVal(elems[0])
    asset = deserialize_asset(elems[1]) if len(elems) > 1 else None
    if asset is None:
        raise ValueError(f'Could not parse asset: {elems[1]}')
    return fval, asset


def serialize_trade(trade: HistoryEvent) -> dict:
    """Legacy function for backwards compatibility.

    HistoryEvent should use serialize_event instead.
    """
    # For now, just return serialize_event output since HistoryEvent
    # doesn't have trade-specific properties
    return serialize_event(trade)


def serialize_ledger_action(action):
    raise NotImplementedError()
    # ser_action = action.serialize()
    # ser_action['timestamp'] = serialize_timestamp(action.timestamp)
    #
    # if action.action_type == LedgerActionType.AIRDROP:
    #     ser_action['airdrop'] = serialize_amount(FVal(action.amount), action.asset)
    #     del ser_action['asset']
    #     del ser_action['amount']
    #     del ser_action['action_type']
    #
    # elif action.action_type == LedgerActionType.INCOME:
    #     ser_action['income'] = serialize_amount(FVal(action.amount), action.asset)
    #     del ser_action['asset']
    #     del ser_action['amount']
    #     del ser_action['action_type']
    #
    # elif action.action_type == LedgerActionType.GIFT:
    #     ser_action['gift'] = serialize_amount(FVal(action.amount), action.asset)
    #     del ser_action['asset']
    #     del ser_action['amount']
    #     del ser_action['action_type']
    #
    # elif action.action_type == LedgerActionType.LOSS:
    #     ser_action['loss'] = serialize_amount(FVal(action.amount), action.asset)
    #     del ser_action['asset']
    #     del ser_action['amount']
    #     del ser_action['action_type']
    #
    # elif action.action_type == LedgerActionType.EXPENSE:
    #     ser_action['expense'] = serialize_amount(FVal(action.amount), action.asset)
    #     del ser_action['asset']
    #     del ser_action['amount']
    #     del ser_action['action_type']
    #
    # if not ser_action['identifier']:
    #     del ser_action['identifier']
    #
    # if not ser_action['location']:
    #     del ser_action['location']
    #
    # if not ser_action['notes']:
    #     del ser_action['notes']
    #
    # if not ser_action['link']:
    #     del ser_action['link']
    #
    # if not ser_action['rate']:
    #     del ser_action['rate']
    #
    # if not ser_action['rate_asset']:
    #     del ser_action['rate_asset']
    #
    # return ser_action


def serialize_trades(trades: List[HistoryEvent]) -> List[dict]:
    def trade_sort_key(trade):
        return (trade.timestamp, trade.group_identifier, trade.sequence_index)

    return [serialize_trade(trade) for trade in sorted(trades, key=trade_sort_key)]


def serialize_ledger_actions(actions) -> List[dict]:
    raise NotImplementedError()
    # return [
    #     serialize_ledger_action(action)
    #     for action in sorted(actions, key=lambda action: (action.timestamp, action.link))
    # ]


def serialize_event(event: HistoryBaseEntry) -> dict:
    ser_event = event.serialize()
    ser_event['timestamp'] = serialize_timestamp_ms(event.timestamp)

    is_evm_event = isinstance(event, EvmEvent)

    if 'entry_type' in ser_event:
        # Entry type is metadata that we don't need to preserve in YAML
        # We handle serialization based on event_type and event_subtype instead
        del ser_event['entry_type']

    if (
        event.event_type == HistoryEventType.SPEND
        and event.event_subtype == HistoryEventSubType.FEE
    ):
        ser_event['spend_fee'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.LOSS
        and event.event_subtype == HistoryEventSubType.LIQUIDATE
    ):
        ser_event['loss'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.TRADE
        and event.event_subtype == HistoryEventSubType.SPEND
    ):
        ser_event['trade_spend'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.SPEND
        and event.event_subtype == HistoryEventSubType.NONE
    ):
        ser_event['spend'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.TRADE
        and event.event_subtype == HistoryEventSubType.RECEIVE
    ):
        ser_event['trade_receive'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.TRADE
        and event.event_subtype == HistoryEventSubType.FEE
    ):
        ser_event['trade_fee'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.RECEIVE
        and event.event_subtype == HistoryEventSubType.NONE
    ):
        if event.location == Location.COINBASE:
            # For coinbase, we assume RECEIVE/NONE is income
            # This is a hack, but we don't have a better way to distinguish
            # TBH this should be handled in the event collector
            ser_event['income'] = serialize_amount(event.amount, event.asset)
        else:
            ser_event['gift'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type in (HistoryEventType.RECEIVE, HistoryEventType.STAKING)
    ) and event.event_subtype == HistoryEventSubType.REWARD:
        ser_event['income'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.RECEIVE
        and event.event_subtype == HistoryEventSubType.AIRDROP
    ):
        ser_event['airdrop'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.DEPOSIT
        and event.event_subtype == HistoryEventSubType.DEPOSIT_ASSET
    ):
        ser_event['deposit'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.WITHDRAWAL
        and event.event_subtype == HistoryEventSubType.REMOVE_ASSET
    ):
        ser_event['withdrawal'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.DEPOSIT
        and event.event_subtype == HistoryEventSubType.FEE
    ):
        ser_event['deposit_fee'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    elif (
        event.event_type == HistoryEventType.WITHDRAWAL
        and event.event_subtype == HistoryEventSubType.FEE
    ):
        ser_event['withdrawal_fee'] = serialize_amount(event.amount, event.asset)
        del ser_event['asset']
        del ser_event['event_type']
        del ser_event['event_subtype']

    if 'identifier' in ser_event:
        del ser_event['identifier']

    if 'location' in ser_event:
        del ser_event['location']

    if 'location_label' in ser_event:
        del ser_event['location_label']

    if is_evm_event:
        if 'tx_ref' in ser_event:
            ser_event['link'] = ser_event['tx_ref']
            del ser_event['tx_ref']
        if 'group_identifier' in ser_event:
            del ser_event['group_identifier']
    else:
        if 'group_identifier' in ser_event:
            if ser_event['group_identifier'] and 'link' not in ser_event:
                ser_event['link'] = ser_event['group_identifier']
            del ser_event['group_identifier']
        if 'event_identifier' in ser_event:
            if ser_event['event_identifier'] and 'link' not in ser_event:
                ser_event['link'] = ser_event['event_identifier']
            del ser_event['event_identifier']

    if 'entry_type' in ser_event:
        del ser_event['entry_type']

    if 'extra_data' in ser_event and not ser_event['extra_data']:
        del ser_event['extra_data']

    if 'event_identifier' in ser_event:
        del ser_event['event_identifier']

    if 'product' in ser_event and not ser_event['product']:
        del ser_event['product']

    if 'address' in ser_event and not ser_event['address']:
        del ser_event['address']

    if 'user_notes' in ser_event and not ser_event['user_notes']:
        del ser_event['user_notes']

    if not is_evm_event and 'sequence_index' in ser_event and not ser_event['sequence_index']:
        del ser_event['sequence_index']

    preferred_order = [
        # Action keys
        'gift',
        'income',
        'airdrop',
        'deposit',
        'withdrawal',
        'deposit_fee',
        'withdrawal_fee',
        'spend_fee',
        'trade_spend',
        'trade_receive',
        'trade_fee',
        'spend',
        'loss',
        # Regular event keys
        'counterparty',
        'product',
        'address',
        'link',
        'sequence_index',
        'timestamp',
        'extra_data',
        'user_notes',
    ]

    def sort_dict_keys(d: dict) -> dict:
        def get_order_index(key):
            try:
                return preferred_order.index(key)
            except ValueError:
                return len(preferred_order)  # Put unknown keys at the end

        return {key: d[key] for key in sorted(d.keys(), key=get_order_index)}

    return sort_dict_keys(ser_event)


def serialize_events(actions: List[HistoryBaseEntry]) -> List[dict]:
    return [
        serialize_event(action)
        for action in sorted(
            actions,
            key=lambda action: (
                action.get_timestamp(),
                action.group_identifier,
                action.sequence_index,
            ),
        )
    ]


def deserialize_event(event_dict) -> HistoryBaseEntry:  # pylint: disable=too-many-return-statements
    is_evm_event = False
    event_type = None
    event_subtype = None
    amount = None
    asset = None

    # Handle asset movement events first
    if 'deposit' in event_dict:
        amount, asset = deserialize_amount(event_dict['deposit'])
        return AssetMovement(
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.EXTERNAL,  # Default location
            event_subtype=HistoryEventSubType.RECEIVE,
            asset=asset,
            amount=amount,
            notes=event_dict.get('user_notes'),
            extra_data=event_dict.get('extra_data'),
        )

    if 'withdrawal' in event_dict:
        amount, asset = deserialize_amount(event_dict['withdrawal'])
        return AssetMovement(
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.EXTERNAL,  # Default location
            event_subtype=HistoryEventSubType.SPEND,
            asset=asset,
            amount=amount,
            notes=event_dict.get('user_notes'),
            extra_data=event_dict.get('extra_data'),
        )

    if 'deposit_fee' in event_dict:
        amount, asset = deserialize_amount(event_dict['deposit_fee'])
        return AssetMovement(
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.EXTERNAL,  # Default location
            event_subtype=HistoryEventSubType.FEE,
            asset=asset,
            amount=amount,
            notes=event_dict.get('user_notes'),
            extra_data=event_dict.get('extra_data'),
        )

    if 'withdrawal_fee' in event_dict:
        amount, asset = deserialize_amount(event_dict['withdrawal_fee'])
        return AssetMovement(
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.EXTERNAL,  # Default location
            event_subtype=HistoryEventSubType.FEE,
            asset=asset,
            amount=amount,
            notes=event_dict.get('user_notes'),
            extra_data=event_dict.get('extra_data'),
        )

    if 'spend_fee' in event_dict:
        amount, asset = deserialize_amount(event_dict['spend_fee'])
        is_evm_event = True
        event_type = HistoryEventType.SPEND
        event_subtype = HistoryEventSubType.FEE
    elif 'trade_spend' in event_dict:
        amount, asset = deserialize_amount(event_dict['trade_spend'])
        event_type = HistoryEventType.TRADE
        event_subtype = HistoryEventSubType.SPEND
    elif 'trade_receive' in event_dict:
        amount, asset = deserialize_amount(event_dict['trade_receive'])
        event_type = HistoryEventType.TRADE
        event_subtype = HistoryEventSubType.RECEIVE
    elif 'trade_fee' in event_dict:
        amount, asset = deserialize_amount(event_dict['trade_fee'])
        event_type = HistoryEventType.TRADE
        event_subtype = HistoryEventSubType.FEE

    if not is_evm_event:
        is_evm_event = bool(
            event_dict.get('location', '') == 'ethereum' and (event_type and event_subtype)
        )

    if is_evm_event:
        if 'sequence_index' not in event_dict:
            raise ValueError('Missing sequence_index in event: {}'.format(event_dict))

        group_identifier = event_dict.get('group_identifier', event_dict.get('link', ''))

        return EvmEvent(
            tx_ref=deserialize_evm_tx_hash(
                group_identifier[2:] if group_identifier.startswith('0x') else group_identifier
            ),
            sequence_index=event_dict['sequence_index'],
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.ETHEREUM,
            event_type=event_type,
            event_subtype=event_subtype,
            asset=asset,
            amount=amount,
            location_label=None,
            notes=' '.join(filter(None, [event_dict.get('notes'), event_dict.get('user_notes')]))
            or None,
            identifier=None,
            counterparty=event_dict.get('counterparty'),
            address=event_dict.get('address'),
            extra_data=None,
        )

    # If we have trade event info but it's not an EVM event, create a SwapEvent
    if event_type == HistoryEventType.TRADE and event_subtype is not None:
        return SwapEvent(
            group_identifier=str(event_dict.get('group_identifier', event_dict.get('link', ''))),
            sequence_index=event_dict.get('sequence_index'),
            timestamp=TimestampMS(deserialize_timestamp_ms(event_dict['timestamp'])),
            location=Location.deserialize(event_dict.get('location') or 'external'),
            event_subtype=event_subtype,
            asset=asset,
            amount=amount,
            notes=event_dict.get('user_notes'),
        )

    return deserialize_ledger_action(event_dict)
    # return HistoryEvent(
    #     event_identifier=event_dict.get('link', '').encode(),
    #     sequence_index=event_dict['sequence_index'],
    #     timestamp=deserialize_timestamp_ms(event_dict['timestamp']),
    #     location=Location.ETHEREUM,
    #     event_type=HistoryEventType.SPEND,
    #     event_subtype=HistoryEventSubType.FEE,
    #     asset=asset,
    #     amount=Balance(amount, 0),
    #     location_label=None,
    #     notes=event_dict.get('notes'),
    #     counterparty=event_dict.get('counterparty'),
    #     identifier=None,
    #     extra_data=None
    # )


def deserialize_tradetype(trade_type: str) -> EventDirection:
    if trade_type == 'sell':
        return EventDirection.OUT

    if trade_type == 'buy':
        return EventDirection.IN

    raise ValueError(trade_type)


def deserialize_fval(val: str) -> FVal:
    return FVal(val)


def serialize_fval(val: FVal) -> str:
    return str(val)


ASSET_RE = re.compile(r'^([^\[]*)(\[(.*)\])?')


def deserialize_identifier(val: str) -> str:
    match = ASSET_RE.match(val)
    if match is None:
        raise ValueError(f'Could not parse asset: {val}')

    symbol, _identifier_outer, identifier = match.groups()
    if identifier:
        return identifier
    return symbol


def deserialize_asset(val: str) -> Asset:
    asset = None
    match = ASSET_RE.match(val)
    if match is None:
        raise ValueError(f'Could not parse asset: {val}')

    symbol, _identifier_outer, identifier = match.groups()
    if identifier:
        asset = Asset(identifier).resolve()
    elif symbol:
        try:
            asset = symbol_to_asset_or_token(symbol)
        except UnknownAsset:
            try:
                asset = symbol_to_asset_or_token(symbol, chain_id=ChainID.ETHEREUM)
            except UnknownAsset:
                asset = None

    if asset is None:
        raise ValueError(f'Symbol not found or ambigous: {val}')

    return asset


def deserialize_evm_token(token_data: AssetConfig) -> EvmToken:
    token = EvmToken.initialize(
        address=deserialize_evm_address(token_data.address),
        name=token_data.name,
        symbol=token_data.symbol,
        decimals=token_data.decimals,
        coingecko=token_data.coingecko,
        chain_id=ChainID(token_data.chain_id) if token_data.chain_id else ChainID.ETHEREUM,
        token_kind=TokenKind.ERC20,
    )
    return token


def serialize_nft(nft: Nfts) -> Dict[str, Any]:
    obj = nft.serialize()
    return {
        'name': obj['name'],
        'collection_name': obj['collection']['name'],
        'id': obj['token_identifier'],
    }


def serialize_nfts(nfts: List[Nfts]) -> List[Dict[str, Any]]:
    return [serialize_nft(nft) for nft in sorted(nfts, key=lambda nft: nft.token_identifier)]


def deserialize_missing_price(missing_price: MissingPrice) -> dict:
    return {
        'from': serialize_asset(missing_price.from_asset),
        'to': serialize_asset(missing_price.to_asset),
        'at': serialize_timestamp(missing_price.time),
        'price': serialize_fval(ZERO),
    }
