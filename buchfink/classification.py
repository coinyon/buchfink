import logging
from typing import List

from rotkehlchen.typing import EthereumTransaction
from rotkehlchen.utils.misc import hexstr_to_int

from buchfink.account import Account
from buchfink.datatypes import Asset, FVal, LedgerAction, LedgerActionType

logger = logging.getLogger(__name__)

CLAIMED = '0x4ec90e965519d92681267467f775ada5bd214aa92c0dc93d90a5e880ce9ed026'
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
REWARD_PAID = '0xe2403640ba68fed3a2f88b7557551d1993f84b99bb10ff833f0cf8db0c5e0486'

ADDR_UNISWAP_AIRDROP = '0x090D4613473dEE047c3f2706764f49E0821D256e'
ADDR_MIRROR_AIRDROP = '0x2A398bBa1236890fb6e9698A698A393Bb8ee8674'
ADDR_PIEDAO_INCENTIVES = '0x8314337d2b13e1A61EadF0FD1686b2134D43762F'
ADDR_PIEDAO_INCENTIVES2 = '0xb9a4bca06f14a982fcd14907d31dfacadc8ff88e'
ADDR_INDEX_REWARDS = '0x8f06FBA4684B5E0988F215a47775Bb611Af0F986'
ADDR_YFI_GOVERNANCE = '0xba37b002abafdd8e89a1995da52740bbc013d992'
ADDR_CREAM_REWARDS = '0x224061756c150e5048a1e4a3e6e066db35037462'
ADDR_CREAM_7DAY_LOCK = '0x3ba3c0e8a9e5f4a01ce8e086b3d8e8a603a2129e'
ADDR_POOL_AIRDROP = '0xBE1a33519F586A4c8AA37525163Df8d67997016f'


def classify_tx(account: Account, tx_hash: str, txn: EthereumTransaction, receipt: dict) \
        -> List[LedgerAction]:
    actions = []  # type: List[LedgerAction]

    if txn.from_address != account.address:
        return actions

    for event in receipt['logs']:
        amount = hexstr_to_int(event['data'][130:])
        if event['topics'][0] == CLAIMED and event['address'] == ADDR_UNISWAP_AIRDROP.lower():
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('UNI'),
                notes='',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED and event['address'] == ADDR_MIRROR_AIRDROP.lower():
            amount = hexstr_to_int(event['data'][130:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('MIR'),
                notes='',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED and event['address'] == ADDR_POOL_AIRDROP.lower():
            amount = hexstr_to_int(event['data'][130:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('POOL'),
                notes='PoolTogether airdrop',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED:
            logger.warn('Unknown Claimed event for tx: %s', tx_hash)

        if event['topics'][0] == REWARD_PAID and event['address'] in (ADDR_PIEDAO_INCENTIVES.lower(), ADDR_PIEDAO_INCENTIVES2):
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('DOUGH'),
                notes='rewards for providing liquidity',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID and event['address'] == ADDR_INDEX_REWARDS.lower():
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('INDEX'),
                notes='rewards for providing liquidity',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID and event['address'] == ADDR_YFI_GOVERNANCE.lower():
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('yDAI+yUSDC+yUSDT+yTUSD'),
                notes='rewards from yearn governance',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID and event['address'] in (ADDR_CREAM_REWARDS, ADDR_CREAM_7DAY_LOCK):
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                timestamp=txn.timestamp,
                asset=Asset('CREAM'),
                notes='rewards from cream incentives',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID:
            logger.warn('Unknown RewardPaid event for tx: %s', tx_hash)

    return actions
