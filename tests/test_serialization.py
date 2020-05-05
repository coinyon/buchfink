from datetime import datetime, timezone

import pytest

from buchfink.datatypes import Asset, FVal, Trade, TradeType
from buchfink.serialization import deserialize_trade, serialize_trade
from rotkehlchen.serialization.deserialize import deserialize_timestamp_from_date


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


def test_datetime_deserialization():
    ts = deserialize_timestamp_from_date('2020-05-05T09:48:52Z', 'iso8601', 'coinbase')
    dt = datetime.fromtimestamp(ts, timezone.utc)
    assert dt.year == 2020
    assert dt.month == 5
    assert dt.day == 5
