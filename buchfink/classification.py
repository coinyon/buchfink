import logging
from typing import List

from rotkehlchen.assets.utils import symbol_to_asset_or_token
from rotkehlchen.typing import EthereumTransaction
from rotkehlchen.utils.misc import hexstr_to_int

from buchfink.account import Account
from buchfink.datatypes import FVal, LedgerAction, LedgerActionType
from buchfink.serialization import serialize_timestamp

logger = logging.getLogger(__name__)

CLAIMED = '0x4ec90e965519d92681267467f775ada5bd214aa92c0dc93d90a5e880ce9ed026'
CLAIMED_2 = '0xd8138f8a3f377c5259ca548e70e4c2de94f129f5a11036a15b69513cba2b426a'
CLAIMED_3 = '0x6f9c9826be5976f3f82a3490c52a83328ce2ec7be9e62dcb39c26da5148d7c76'
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
REWARD_PAID = '0xe2403640ba68fed3a2f88b7557551d1993f84b99bb10ff833f0cf8db0c5e0486'
MINTED = '0x9d228d69b5fdb8d273a2336f8fb8612d039631024ea9bf09c424a9503aa078f0'
PURCHASE = '0x2499a5330ab0979cc612135e7883ebc3cd5c9f7a8508f042540c34723348f632'

ADDR_UNISWAP_AIRDROP = '0x090D4613473dEE047c3f2706764f49E0821D256e'
ADDR_MIRROR_AIRDROP = '0x2A398bBa1236890fb6e9698A698A393Bb8ee8674'
ADDR_PIEDAO_INCENTIVES = (
    '0x8314337d2b13e1A61EadF0FD1686b2134D43762F'.lower(),
    '0xb9a4bca06f14a982fcd14907d31dfacadc8ff88e'
)
ADDR_INDEX_REWARDS = '0x8f06FBA4684B5E0988F215a47775Bb611Af0F986'
ADDR_YFI_GOVERNANCE = '0xba37b002abafdd8e89a1995da52740bbc013d992'
ADDR_CREAM_REWARDS = (
    '0x224061756c150e5048a1e4a3e6e066db35037462',
    '0x3ba3c0e8a9e5f4a01ce8e086b3d8e8a603a2129e'
)
ADDR_BALANCER_REWARDS = '0x6d19b2bF3A36A61530909Ae65445a906D98A2Fa8'
ADDR_POOL_AIRDROP = '0xBE1a33519F586A4c8AA37525163Df8d67997016f'
ADDR_BADGER_TREE = '0x660802Fc641b154aBA66a62137e71f331B6d787A'
ADDR_BADGER = '0x3472A5A71965499acd81997a54BBA8D852C6E53d'
ADDR_MIR_REWARDS = '0x5d447Fc0F8965cED158BAB42414Af10139Edf0AF'
ADDR_XTOKEN_AIRDROP = '0x11f10378fc56277eEdBc0c3309c457b0fd5c6dfd'
ADDR_SWERVE_MINTER = '0x2c988c3974ad7e604e276ae0294a7228def67974'
ADDR_FEI_GENESIS_GROUP = '0xBFfB152b9392e38CdDc275D818a3Db7FE364596b'
ADDR_DODO_REWARDS = '0x0e504d3e053885a82bd1cb5c29cbaae5b3673be4'
ADDR_DODO = '0x43Dfc4159D86F3A37A5A4B3D4580b888ad7d4DDd'


def classify_tx(account: Account, tx_hash: str, txn: EthereumTransaction, receipt: dict) \
        -> List[LedgerAction]:
    actions = []  # type: List[LedgerAction]

    tx_time = serialize_timestamp(txn.timestamp)

    if txn.from_address != account.address:
        return actions

    for event in receipt['logs']:
        if event['topics'][0] == CLAIMED and event['address'] == ADDR_UNISWAP_AIRDROP.lower():
            amount = hexstr_to_int(event['data'][130:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x1f9840a85d5af5bf1d1762f925bdaddc4201f984'),
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
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x09a3ecafa817268f77be1283176b946c4ff2e608'),
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
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x0cec1a9154ff802e7934fc916ed7ca50bde6844e'),
                notes='PoolTogether airdrop',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED:
            logger.warning('Unknown Claimed event for tx %s at %s', tx_hash, tx_time)

        if event['topics'][0] == CLAIMED_3 and event['address'] == ADDR_BADGER_TREE.lower():
            if hexstr_to_int(event['topics'][2]) == hexstr_to_int(ADDR_BADGER):
                amount = hexstr_to_int(event['data'][2:66])
                token = symbol_to_asset_or_token('_ceth_0x3472a5a71965499acd81997a54bba8d852c6e53d')
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.INCOME,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=token,
                    notes='Badger rewards for staking',
                    link=tx_hash
                )]

        elif event['topics'][0] == CLAIMED_3:
            logger.warning('Unknown Claimed event for tx %s at %s', tx_hash, tx_time)

        if event['topics'][0] == CLAIMED_2 and event['address'] == ADDR_XTOKEN_AIRDROP.lower():
            amount = hexstr_to_int(event['data'])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x7f3edcdd180dbe4819bd98fee8929b5cedb3adeb'),
                notes='xToken airdrop',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED_2 and event['address'] == ADDR_BALANCER_REWARDS.lower():
            amount = hexstr_to_int(event['data'][66:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('BAL'),
                notes='Balancer rewards for providing liquidity',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED_2:
            logger.warning('Unknown Claimed event for tx: %s', tx_hash)

        if event['topics'][0] == REWARD_PAID and event['address'] in ADDR_PIEDAO_INCENTIVES:
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('DOUGH'),
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
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('INDEX'),
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
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('yDAI+yUSDC+yUSDT+yTUSD'),
                notes='rewards from yearn governance',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID and event['address'] in ADDR_CREAM_REWARDS:
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('CREAM'),
                notes='rewards from cream incentives',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID and event['address'] == ADDR_MIR_REWARDS.lower():
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x09a3ecafa817268f77be1283176b946c4ff2e608'),
                notes='rewards for staking MIR LP',
                link=tx_hash
            )]

        elif event['topics'][0] == REWARD_PAID:
            logger.warning('Unknown RewardPaid event for tx %s at %s', tx_hash, tx_time)

        if event['topics'][0] == MINTED and event['address'] == ADDR_SWERVE_MINTER.lower():
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'][66:])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.INCOME,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=symbol_to_asset_or_token('SWRV'),
                    notes='Swerve rewards for pooling liquidity',
                    link=tx_hash
                )]

        elif event['topics'][0] == MINTED:
            logger.warning('Unknown Minted event for tx %s at %s', tx_hash, tx_time)

        if event['topics'][0] == PURCHASE and event['address'] == ADDR_FEI_GENESIS_GROUP.lower():
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.EXPENSE,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=symbol_to_asset_or_token('ETH'),
                    notes='Fei Genesis Commit',
                    link=tx_hash
                )]

        elif event['topics'][0] == PURCHASE:
            logger.warning('Unknown Purchase event for tx %s at %s', tx_hash, tx_time)

        if event['topics'][0] == TRANSFER and event['address'] == ADDR_DODO.lower():
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(ADDR_DODO_REWARDS) and \
                    hexstr_to_int(event['topics'][2]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.INCOME,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=symbol_to_asset_or_token('DODO'),
                    notes='Claim DODO rewards',
                    link=tx_hash
                )]

    return actions
