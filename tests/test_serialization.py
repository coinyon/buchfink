import os.path
import shutil
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from rotkehlchen.serialization.deserialize import deserialize_timestamp_from_date

from buchfink.datatypes import Asset, Balance, FVal, Trade, TradeType
from buchfink.db import BuchfinkDB
from buchfink.serialization import (
    deserialize_asset,
    deserialize_balance,
    deserialize_trade,
    serialize_asset,
    serialize_balance,
    serialize_decimal,
    serialize_trade
)


@pytest.fixture
def dummy_trade():
    return Trade(
        datetime(2020, 1, 3, tzinfo=timezone.utc).timestamp(),
        'coinbase',
        Asset('BTC'),
        Asset('EUR'),
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


def test_trade_serialization_2(dummy_trade):
    assert serialize_decimal(Decimal('1234.234e-10')) == '0.0000001234234'
    assert serialize_decimal(Decimal('1234.23410')) == '1234.2341'


def test_trade_deserialization_with_fee(tmp_path, dummy_trade):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
            os.path.join(tmp_path, 'buchfink')
    )

    BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

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


def test_assets_serialization(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))

    A_BCH = buchfink_db.get_asset_by_symbol('BCH')
    assert A_BCH == Asset('BCH')
    assert 'BCH' in serialize_asset(A_BCH)

    A_ETH = buchfink_db.get_asset_by_symbol('ETH')
    assert A_ETH == Asset('ETH')
    assert 'ETH' in serialize_asset(A_ETH)

    A_DAI = buchfink_db.get_asset_by_symbol('DAI')
    assert A_DAI is not None
    assert 'DAI' in serialize_asset(A_DAI)

    assert deserialize_asset(serialize_asset(Asset('ETH'))) == Asset('ETH')

    A_HEX = buchfink_db.get_asset_by_symbol('HEX')
    assert A_HEX is not None
    assert 'HEX' in serialize_asset(A_HEX)

    A_STAKEDAO = buchfink_db.get_asset_by_symbol(
            'eip155:1/erc20:0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F'
    )
    assert deserialize_asset(serialize_asset(A_STAKEDAO)) == A_STAKEDAO
    assert 'SDT' in serialize_asset(A_STAKEDAO)

    A_STAKEDAO = buchfink_db.get_asset_by_symbol(
            'SDT[eip155:1/erc20:0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F]'
    )
    assert deserialize_asset(serialize_asset(A_STAKEDAO)) == A_STAKEDAO
    assert 'SDT' in serialize_asset(A_STAKEDAO)


def test_serialize_deserialize_balance(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    bal = serialize_balance(Balance(FVal('0.5')), Asset('ETH'))
    balance, asset = deserialize_balance(bal, buchfink_db)
    assert str(balance.amount) == '0.5'
    assert asset == Asset('ETH')


def test_serialize_deserialize_balance_secondary(tmp_path):
    shutil.copytree(
            os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
            os.path.join(tmp_path, 'buchfink')
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    A_STAKEDAO = buchfink_db.get_asset_by_symbol(
            'eip155:1/erc20:0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F'
    )
    bal = serialize_balance(Balance(FVal('1.5')), A_STAKEDAO)
    balance, asset = deserialize_balance(bal, buchfink_db)
    assert str(balance.amount) == '1.5'
    assert asset == A_STAKEDAO
