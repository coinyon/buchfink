import os.path
from datetime import datetime

from buchfink.db import BuchfinkDB
from buchfink.datatypes import FVal


def test_ethereum_balances():
    start_ts = datetime.fromisoformat('2015-01-01').timestamp()
    end_ts = datetime.fromisoformat('2019-01-01').timestamp()

    buchfink_db = BuchfinkDB(os.path.join(os.path.dirname(__file__), 'scenarios', 'ethereum'))
    whale = buchfink_db.get_all_accounts()[0]
    sheet = buchfink_db.query_balances(whale)
    assert sheet.assets['ETH'].amount == FVal('147699.424503407102942053')
