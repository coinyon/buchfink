from datetime import datetime, timezone
from decimal import Decimal

import pytest
from rotkehlchen.serialization.deserialize import deserialize_timestamp_from_date

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.serialization import (deserialize_trade, serialize_decimal, serialize_trade)


@pytest.fixture
def dummy_trade():
    return Trade(
        datetime(2020, 1, 3, tzinfo=timezone.utc).timestamp(),
        'coinbase',
        'BTC_EUR',
        TradeType.BUY,
        FVal('0.52'),
        FVal('7200.0'),
        FVal('0.5'),
        Asset('EUR'),
        'LINK-123'
    )


def test_trade_serialization(dummy_trade):
    ser_trade = serialize_trade(dummy_trade)

    assert ser_trade['buy'] == '0.52 BTC'
    assert ser_trade['for'] == '3744 EUR'
    assert ser_trade['fee'] == '0.5 EUR'

    trade = deserialize_trade(ser_trade)

    assert dummy_trade == trade


def test_trade_serialization(dummy_trade):
    assert serialize_decimal(Decimal('1234.234e-10')) == '0.0000001234234'
    assert serialize_decimal(Decimal('1234.23410')) == '1234.2341'


def test_trade_deserialization_with_fee(dummy_trade):
    ser_trade = serialize_trade(dummy_trade)

    del ser_trade['fee']

    trade = deserialize_trade(ser_trade)

    assert trade.fee == 0


@pytest.mark.skip
def test_trade_deserialization_various_assets(dummy_trade):
    "test if some assets are correctly detected"
    trade = deserialize_trade({'buy': '1 BCH', 'for': '1 ETH', 'timestamp': '2017-01-01'})
    assert trade.fee == 0

    trade = deserialize_trade({'buy': '1 BLX', 'for': '1 ETH', 'timestamp': '2017-01-01'})
    assert trade.fee == 0


def test_datetime_deserialization():
    ts = deserialize_timestamp_from_date('2020-05-05T09:48:52Z', 'iso8601', 'coinbase')
    dt = datetime.fromtimestamp(ts, timezone.utc)
    assert dt.year == 2020
    assert dt.month == 5
    assert dt.day == 5
