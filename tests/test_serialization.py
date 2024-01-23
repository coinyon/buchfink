import os.path
import shutil
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import yaml
from rotkehlchen.serialization.deserialize import deserialize_timestamp_from_date
from rotkehlchen.types import Location, TimestampMS
from rotkehlchen.utils.misc import ts_sec_to_ms

from buchfink.datatypes import (
    Asset,
    Balance,
    BalanceSheet,
    EvmEvent,
    FVal,
    HistoryEvent,
    HistoryEventSubType,
    HistoryEventType,
    Trade,
    TradeType,
)
from buchfink.db import BuchfinkDB
from buchfink.models.config import AssetConfig
from buchfink.serialization import (
    deserialize_amount,
    deserialize_asset,
    deserialize_balance,
    deserialize_event,
    deserialize_evm_token,
    deserialize_trade,
    serialize_asset,
    serialize_balance,
    serialize_balances,
    serialize_decimal,
    serialize_event,
    serialize_trade,
)


@pytest.fixture
def dummy_trade():
    return Trade(
        datetime(2020, 1, 3, tzinfo=timezone.utc).timestamp(),
        Location.COINBASE,
        Asset('BTC'),
        Asset('EUR'),
        TradeType.BUY,
        FVal('0.52'),
        FVal('7200.0'),
        FVal('0.5'),
        Asset('EUR'),
        'LINK-123',
    )


@pytest.fixture
def buchfink_db(tmp_path):
    # An empty buchfink DB, created at tmp_path
    # For now we use bullrun scenario, but we should create an empty scenario
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'bullrun'),
        os.path.join(tmp_path, 'buchfink'),
    )
    yield BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))


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
        os.path.join(tmp_path, 'buchfink'),
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
        os.path.join(tmp_path, 'buchfink'),
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
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    bal = serialize_balance(Balance(FVal('0.5')), Asset('ETH'))
    balance, asset = deserialize_balance(bal, buchfink_db)
    assert str(balance.amount) == '0.5'
    assert asset == Asset('ETH')


def test_serialize_deserialize_balance_secondary(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    A_STAKEDAO = buchfink_db.get_asset_by_symbol(
        'eip155:1/erc20:0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F'
    )
    bal = serialize_balance(Balance(FVal('1.5')), A_STAKEDAO)
    balance, asset = deserialize_balance(bal, buchfink_db)
    assert str(balance.amount) == '1.5'
    assert asset == A_STAKEDAO


def test_serialize_balance_sheet(buchfink_db):
    A_HEX = buchfink_db.get_asset_by_symbol('HEX')
    bs = BalanceSheet(
        assets={
            A_HEX: Balance(FVal('1500')),
        }
    )

    serialized = str(serialize_balances(bs))
    assert 'HEX' in serialized
    assert '1500' in serialized


def test_load_yaml_parse_action_and_deserialize(buchfink_db):
    yaml_content = """
- spend_fee: 0.0203523 ETH
  counterparty: gas
  link: '0x1234'
  notes: Burned 0.0203523 ETH in gas
  sequence_index: 0
  timestamp: '2021-08-19T10:15:50+00:00'"""
    action = deserialize_event(yaml.safe_load(yaml_content)[0])
    assert isinstance(action, EvmEvent)
    dict_action = serialize_event(action)
    assert dict_action['spend_fee'] == '0.0203523 ETH'
    assert dict_action['counterparty'] == 'gas'
    assert dict_action['link'] == '0x1234'
    assert dict_action['notes'] == 'Burned 0.0203523 ETH in gas'
    assert dict_action['sequence_index'] == 0
    assert dict_action['timestamp'] == '2021-08-19T10:15:50+00:00'
    assert set(dict_action.keys()) == {
        'spend_fee',
        'counterparty',
        'link',
        'notes',
        'sequence_index',
        'timestamp',
    }


def test_deserialize_asset_without_name(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), 'scenarios', 'mappings'),
        os.path.join(tmp_path, 'buchfink'),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, 'buchfink/buchfink.yaml'))
    A_WBTC = buchfink_db.get_asset_by_symbol('WBTC')

    with pytest.raises(ValueError):
        # Missing ] at the end
        deserialize_amount('1 [eip155:1/erc20:0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599')

    amount, asset = deserialize_amount(
        '1 [eip155:1/erc20:0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599]'
    )
    assert str(amount) == '1'
    assert asset == A_WBTC


def test_serialize_and_deserialize_history_event(buchfink_db):
    A_WBTC = buchfink_db.get_asset_by_symbol('WBTC')
    amount = 42
    ts = ts_sec_to_ms(
        deserialize_timestamp_from_date('2022-05-05T09:48:52Z', 'iso8601', 'coinbase')
    )
    event = HistoryEvent(
        identifier=None,
        sequence_index=0,
        location=Location.COINBASE,
        event_type=HistoryEventType.RECEIVE,
        event_subtype=HistoryEventSubType.AIRDROP,
        balance=Balance(FVal(amount), 0),
        timestamp=ts,
        asset=A_WBTC,
        notes='test 123',
        event_identifier='0x123',
    )
    serialized = serialize_event(event)
    assert serialized['airdrop'] == '42 WBTC'
    assert serialized['link'] == '0x123'
    assert serialized['timestamp'] == '2022-05-05T09:48:52+00:00'
    event_2 = deserialize_event(serialized)
    assert event.event_type == event_2.event_type
    assert event.event_subtype == event_2.event_subtype

    # roundtrip should be the same
    serialized_2 = serialize_event(event_2)
    assert serialized_2 == serialized


def test_serialize_and_deserialize_history_event_loss(buchfink_db):
    A_WBTC = buchfink_db.get_asset_by_symbol('WBTC')
    amount = 42
    ts = deserialize_timestamp_from_date('2022-05-05T09:48:52Z', 'iso8601', 'coinbase')
    event = HistoryEvent(
        identifier=None,
        sequence_index=0,
        location=Location.COINBASE,
        event_type=HistoryEventType.SPEND,
        event_subtype=HistoryEventSubType.LIQUIDATE,
        balance=Balance(FVal(amount), 0),
        timestamp=TimestampMS(ts),
        asset=A_WBTC,
        notes='test 123',
        event_identifier='0x0',
    )
    serialized = serialize_event(event)
    assert serialized['loss'] == '42 WBTC'
    event_2 = deserialize_event(serialized)
    assert event.event_type == event_2.event_type
    assert event.event_subtype == event_2.event_subtype
    # TODO assert event.location == event_2.location


def test_evm_token_on_polygon():
    deserialized = deserialize_evm_token(
        AssetConfig(
            address='0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
            chain_id=137,
            decimals=18,
            name='Wrapped Ether',
            symbol='WETH',
            type='ethereum',
        )
    )
    assert str(deserialized.chain_id) == 'polygon_pos'
    assert deserialized.identifier == 'eip155:137/erc20:0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619'
