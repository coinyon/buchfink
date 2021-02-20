from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import dateutil.parser

from buchfink.datatypes import (AMMTrade, Asset, Balance, FVal, LedgerAction,
                                LedgerActionType, Trade, TradeType)


def serialize_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def deserialize_timestamp(timestamp: str) -> int:
    return int(datetime.fromisoformat(timestamp).timestamp())


def deserialize_ledger_action(action_dict) -> LedgerAction:
    if 'income' in action_dict:
        amount, asset = deserialize_amount(action_dict['income'])
        return LedgerAction(
            identifier=None,
            location='',
            action_type=LedgerActionType.INCOME,
            amount=amount,
            timestamp=deserialize_timestamp(action_dict['timestamp']),
            asset=asset,
            notes=action_dict.get('notes', ''),
            link=action_dict.get('link', '')
        )

    if 'airdrop' in action_dict:
        amount, asset = deserialize_amount(action_dict['airdrop'])
        return LedgerAction(
            identifier=None,
            location='',
            action_type=LedgerActionType.AIRDROP,
            amount=amount,
            timestamp=deserialize_timestamp(action_dict['timestamp']),
            asset=asset,
            notes=action_dict.get('notes', ''),
            link=action_dict.get('link', '')
        )

    if 'gift' in action_dict:
        amount, asset = deserialize_amount(action_dict['gift'])
        return LedgerAction(
            identifier=None,
            location='',
            action_type=LedgerActionType.GIFT,
            amount=amount,
            timestamp=deserialize_timestamp(action_dict['timestamp']),
            asset=asset,
            notes=action_dict.get('notes', ''),
            link=action_dict.get('link', '')
        )

    raise ValueError(f'Unable to parse ledger action: {action_dict}')


def deserialize_trade(trade_dict) -> Trade:
    if 'pair' in trade_dict:
        return Trade(
            trade_dict['timestamp'],
            trade_dict.get('location', ''),
            trade_dict['pair'],
            deserialize_tradetype(trade_dict['trade_type']),
            deserialize_fval(trade_dict['amount']),
            deserialize_fval(trade_dict['rate']),
            deserialize_fval(trade_dict['fee']),
            deserialize_asset(trade_dict['fee_currency']),
            trade_dict['link']
        )

    if 'buy' in trade_dict:
        trade_type = TradeType.BUY
        amount, base_asset = deserialize_amount(trade_dict['buy'])
    elif 'sell' in trade_dict:
        trade_type = TradeType.SELL
        amount, base_asset = deserialize_amount(trade_dict['sell'])
    else:
        raise ValueError('Invalid trade: ' + str(trade_dict))

    quote_amount, quote_asset = deserialize_amount(trade_dict['for'])

    if base_asset is None:
        raise ValueError('No base asset provided')

    if quote_asset is None:
        raise ValueError('No quote asset provided')

    if 'fee' in trade_dict:
        fee, fee_currency = deserialize_amount(trade_dict['fee'])
    else:
        fee, fee_currency = FVal('0'), quote_asset

    return Trade(
        dateutil.parser.isoparse(trade_dict['timestamp']).timestamp(),
        trade_dict.get('location', ''),
        '{0}_{1}'.format(base_asset.identifier, quote_asset.identifier),
        trade_type,
        amount,
        quote_amount / amount,
        fee,
        fee_currency,
        trade_dict.get('link', '')
    )


QUANT_DECIMAL = Decimal('0.00000000000001')


def serialize_decimal(dec: Decimal) -> str:
    'return a nice, non-scientific, non-trailing-zero number representation'
    ser_amount = str(dec.quantize(QUANT_DECIMAL))
    if 'E' in ser_amount or 'e' in ser_amount:
        ser_amount = '{0:.14f}'.format(float(dec))
    return ser_amount.rstrip('0').rstrip('.')


def serialize_amount(amount: FVal, asset: Asset) -> str:
    return '{0} {1}'.format(serialize_decimal(amount.num), str(asset.identifier))


def serialize_balance(balance: Balance, asset: Asset) -> dict:
    return {
        'amount': serialize_decimal(balance.amount.num),
        'asset': asset.identifier
    }


def deserialize_balance(balance: Dict[str, Any], inquirer: Optional[Any] = None) \
        -> Tuple[Balance, Asset]:
    amount = FVal(balance['amount'])
    asset = Asset(balance['asset'])
    if inquirer:
        usd_value = amount * inquirer.find_usd_price(asset)
        return Balance(amount, usd_value), asset
    return Balance(amount), asset


def deserialize_amount(amount: str) -> Tuple[FVal, Optional[Asset]]:
    elems = amount.split(' ')
    amount = FVal(elems[0])
    asset = Asset(elems[1]) if len(elems) > 1 else None
    return amount, asset


def serialize_trade(trade: Union[Trade, AMMTrade]):
    ser_trade = trade.serialize()
    ser_trade = {
        'timestamp': serialize_timestamp(trade.timestamp),
        'for': serialize_amount(trade.rate * trade.amount, trade.quote_asset),
    }

    if isinstance(trade, AMMTrade):
        ser_trade['link'] = trade.tx_hash
    else:
        ser_trade['link'] = trade.link

    if trade.fee and trade.fee > 0:
        ser_trade['fee'] = serialize_amount(trade.fee, trade.fee_currency)

    if trade.trade_type == TradeType.BUY:
        ser_trade['buy'] = serialize_amount(trade.amount, trade.base_asset)
    elif trade.trade_type == TradeType.SELL:
        ser_trade['sell'] = serialize_amount(trade.amount, trade.base_asset)
    else:
        raise ValueError('Do not know how to serialize ' + str(trade.trade_type))

    if trade.location:
        ser_trade['location'] = str(trade.location)

    return ser_trade


def serialize_ledger_action(action: LedgerAction):
    ser_action = action.serialize()
    ser_action['timestamp'] = serialize_timestamp(action.timestamp)

    if action.action_type == LedgerActionType.AIRDROP:
        ser_action['airdrop'] = serialize_amount(FVal(action.amount), action.asset)
        del ser_action['asset']
        del ser_action['amount']

    elif action.action_type == LedgerActionType.AIRDROP:
        ser_action['income'] = serialize_amount(FVal(action.amount), action.asset)
        del ser_action['asset']
        del ser_action['amount']

    if not ser_action['identifier']:
        del ser_action['identifier']

    if not ser_action['location']:
        del ser_action['location']

    return ser_action


def serialize_trades(trades: List[Trade]) -> List[Any]:
    return [
        serialize_trade(trade) for trade in
        sorted(trades, key=lambda trade: trade.timestamp)
    ]


def serialize_ledger_actions(actions: List[LedgerAction]) -> List[Any]:
    return [
        serialize_ledger_action(action) for action in
        sorted(actions, key=lambda action: action.timestamp)
    ]


def deserialize_tradetype(trade_type: str) -> TradeType:
    if trade_type == "sell":
        return TradeType.SELL

    if trade_type == "buy":
        return TradeType.BUY

    raise ValueError(trade_type)


def deserialize_fval(val: str) -> FVal:
    return FVal(val)


def deserialize_asset(val: str) -> Asset:
    return Asset(val)
