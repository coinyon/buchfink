# pylint: skip-file
"Load Zerion export CSV and output trades"
import logging
import os.path
from typing import List

import pandas as pd
from rotkehlchen.errors import UnknownAsset

from buchfink.datatypes import FVal, Trade, TradeType
from buchfink.db import BuchfinkDB
from buchfink.models import Account
from buchfink.serialization import deserialize_timestamp

logger = logging.getLogger(__name__)


def get_trades(account: Account) -> List[Trade]:
    zerion_path = 'zerion/' + account.name + '.csv'
    if not os.path.exists(zerion_path):
        return []
    df = pd.read_csv(zerion_path)

    valid_filter = (df['Status'] == 'Confirmed') & \
            (df['Transaction Type'] == 'Trade') & \
            (df['Application'] == 'Uniswap')

    df = df[valid_filter]
    df.sort_values('Timestamp', inplace=True)
    df.loc[df['Application'].isna(), 'Application'] = ''
    df.loc[df['Buy Currency'].isna(), 'Buy Currency'] = ''
    df.loc[df['Buy Currency Address'].isna(), 'Buy Currency Address'] = ''
    df.loc[df['Sell Currency Address'].isna(), 'Sell Currency Address'] = ''
    df.loc[df['Fee Currency'].isna(), 'Fee Currency'] = ''

    db = BuchfinkDB()

    trades = []
    for row in df.to_dict(orient="records"):
        try:
            if row['Buy Currency Address']:
                base_asset = db.get_asset_by_symbol('_ceth_' + row['Buy Currency Address'])
            else:
                base_asset = db.get_asset_by_symbol(row['Buy Currency'])
            if row['Sell Currency Address']:
                quote_asset = db.get_asset_by_symbol('_ceth_' + row['Sell Currency Address'])
            else:
                quote_asset = db.get_asset_by_symbol(row['Sell Currency'])
            fee_asset = db.get_asset_by_symbol(row['Fee Currency'])
        except (UnknownAsset, ValueError):
            logger.exception(row)
            continue
        trades.append(Trade(
            deserialize_timestamp(row['Timestamp']),
            row['Application'].lower(),
            base_asset,
            quote_asset,
            TradeType.BUY,
            FVal(row['Buy Amount']),
            FVal(row['Sell Amount']) / FVal(row['Buy Amount']),
            FVal(row['Fee Amount']),
            fee_asset,
            row['Tx Hash']
        ))

    return trades
