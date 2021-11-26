import os.path
from datetime import datetime

import pytest

from buchfink.datatypes import FVal
from buchfink.db import BuchfinkDB


@pytest.mark.blockchain_data
def test_ethereum_balances():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    buchfink_db = BuchfinkDB(os.path.join(os.path.dirname(__file__), 'scenarios', 'ethereum', 'buchfink.yaml'))
    whale = buchfink_db.get_all_accounts()[0]
    sheet = buchfink_db.query_balances(whale)
    assert sheet.assets['ETH'].amount == FVal('147699.424503407102942053')


def test_custom_ethereum_token():
    buchfink_db = BuchfinkDB(os.path.join(os.path.dirname(__file__), 'scenarios', 'custom_token', 'buchfink.yaml'))
    buchfink_db.perform_assets_updates()
    assert buchfink_db.get_asset_by_symbol('IMX') is not None
