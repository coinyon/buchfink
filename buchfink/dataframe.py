"""
This file contains queries on BuchfinkDB that return pandas DataFrames.
"""
import logging
from typing import Literal

import pandas as pd
import pandera as pa
from pandera.typing import DataFrame, Index, Series

logger = logging.getLogger(__name__)


class Balances(pa.SchemaModel):
    account_name: Series[str]
    account_type: Series[str]
    asset: Series[str]
    amount: Series[str]
    type: Series[str] = pa.Field(isin=['asset', 'liability'])


def get_balances(db, accs) -> DataFrame[Balances]:
    """
    Return a pandas DataFrame with a list of balances:

        asset: Asset
        account: Account
        amount: FVal
        usd_value: FVal
        type: "asset" | "liability"

    """

    rows = []
    for account in accs:
        sheet = db.get_balances(account)

        for asset, balance in sheet.assets.items():
            rows.append({
                'account_name': account.name,
                'account_type': account.account_type,
                'account_address': account.address,
                'asset': asset,
                'amount': balance.amount,
                'usd_value': balance.usd_value,
                'type': "asset"
            })

        for liability, balance in sheet.liabilities.items():
            rows.append({
                'account_name': account.name,
                'account_type': account.account_type,
                'account_address': account.address,
                'asset': asset,
                'amount': balance.amount,
                'usd_value': balance.usd_value,
                'type': "liability"
            })

    df = DataFrame[Balances](rows)
    print('Top 20 assets')
    print(df.groupby('asset')[['amount', 'usd_value']].sum().sort_values('usd_value', ascending=False)[:20].to_string())

    print()
    print('Percentage per account')
    per_account = df.groupby('account_name')['usd_value'].sum()
    print(pd.DataFrame({'usd_value': per_account, 'percentage': per_account / per_account.sum() * 100}))

    print()
    print('Percentage per account type')
    per_account_type = df.groupby('account_type')['usd_value'].sum()
    print(pd.DataFrame({'usd_value': per_account_type, 'percentage': per_account_type / per_account_type.sum() * 100}))

    return df
