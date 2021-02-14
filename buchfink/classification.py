
from typing import List

from rotkehlchen.typing import EthereumTransaction

from buchfink.account import Account
from buchfink.datatypes import Asset, LedgerAction, LedgerActionType

CLAIMED = '0x4ec90e965519d92681267467f775ada5bd214aa92c0dc93d90a5e880ce9ed026'
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

ADDR_UNISWAP_AIRDROP = '0x090D4613473dEE047c3f2706764f49E0821D256e'


def classify_tx(account: Account, tx_hash: str, txn: EthereumTransaction, receipt: dict) \
        -> List[LedgerAction]:
    actions = []  # type: List[LedgerAction]

    if txn.from_address != account.address:
        return actions

    for event in receipt['logs']:
        if event['topics'][0] == CLAIMED and event['address'] == ADDR_UNISWAP_AIRDROP.lower():
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=400,
                timestamp=txn.timestamp,
                asset=Asset('UNI'),
                notes='',
                link=tx_hash
            )]

    return actions
