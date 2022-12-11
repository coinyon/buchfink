import os.path
import shutil

import pytest
from rotkehlchen.types import SupportedBlockchain

from buchfink.datatypes import FVal
from buchfink.db import BuchfinkDB


@pytest.mark.blockchain_data
def test_ethereum_balances():
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
        buchfink_db.get_asset_by_symbol(
            "eip155:1/erc20:0x7b35Ce522CB72e4077BaeB96Cb923A5529764a00"
        ) is not None
    )
    assert buchfink_db.get_asset_by_symbol("FANTASY") is not None


def test_if_we_have_enough_rpc_nodes(tmp_path):
    # This test asserts that after initialization we have some web3 nodes so
    # that our queries will succeed. This test exists because the way that web3 nodes
    # get registred is a little hacky ("migration_4")
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "scenarios", "custom_token"),
        os.path.join(tmp_path, "buchfink"),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, "buchfink/buchfink.yaml"))
    assert len(buchfink_db.get_rpc_nodes(
        blockchain=SupportedBlockchain.ETHEREUM,
        only_active=True
    )) >= 5


def test_if_ignored_assets_are_added(tmp_path):
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "scenarios", "ignored_assets"),
        os.path.join(tmp_path, "buchfink"),
    )
    buchfink_db = BuchfinkDB(os.path.join(tmp_path, "buchfink/buchfink.yaml"))
    buchfink_db.sync_config_assets()
    with buchfink_db.conn.read_ctx() as cursor:
        ignored_assets = buchfink_db.get_ignored_assets(cursor)
        ignored_identifiers = {asset.identifier for asset in ignored_assets}

    assert len(ignored_assets) >= 3
    assert 'eip155:1/erc20:0x426CA1eA2406c07d75Db9585F22781c096e3d0E0' in ignored_identifiers
