import os.path
import shutil
from datetime import datetime

import pytest

from buchfink.datatypes import FVal
from buchfink.db import BuchfinkDB


@pytest.mark.blockchain_data
def test_ethereum_balances():
    start_ts = datetime.fromisoformat("2015-01-01").timestamp()
    end_ts = datetime.fromisoformat("2019-01-01").timestamp()

    buchfink_db = BuchfinkDB(
        os.path.join(os.path.dirname(__file__), "scenarios", "ethereum", "buchfink.yaml")
    )
    whale = buchfink_db.get_all_accounts()[0]
    sheet = buchfink_db.query_balances(whale)
    assert sheet.assets["ETH"].amount == FVal("147699.424503407102942053")


def test_custom_ethereum_token(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "scenarios", "custom_token"),
        os.path.join(tmp_path, "buchfink"),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, "buchfink/buchfink.yaml"))
    buchfink_db.perform_assets_updates()
    assert (
        buchfink_db.get_asset_by_symbol("_ceth_0x7b35Ce522CB72e4077BaeB96Cb923A5529764a00")
        is not None
    )
    assert buchfink_db.get_asset_by_symbol("FANTASY") is not None


def test_if_we_have_enough_web3_nodes(tmp_path):
    # This test asserts that after initialization we have some web3 nodes so
    # that our queries will succeed. This test exists because the way that web3 nodes
    # get registred is a little hacky ("migration_4")
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "scenarios", "custom_token"),
        os.path.join(tmp_path, "buchfink"),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, "buchfink/buchfink.yaml"))
    assert len(buchfink_db.get_web3_nodes(only_active=True)) >= 5
