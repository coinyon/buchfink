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
CLAIMED_4 = '0x04672052dcb6b5b19a9cc2ec1b8f447f1f5e47b5e24cfa5e4ffb640d63ca2be7'
CLAIMED_5 = '0x528937b330082d892a98d4e428ab2dcca7844b51d227a1c0ae67f0b5261acbd9'
TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
REWARD_PAID = '0xe2403640ba68fed3a2f88b7557551d1993f84b99bb10ff833f0cf8db0c5e0486'
MINTED = '0x9d228d69b5fdb8d273a2336f8fb8612d039631024ea9bf09c424a9503aa078f0'
PURCHASE = '0x2499a5330ab0979cc612135e7883ebc3cd5c9f7a8508f042540c34723348f632'
HUNT = '0x8eaf15614908a4e9022141fe4a596b1ab0cb72ab32b25023e3da2a459c9a335c'
STAKEEND = '0x72d9c5a7ab13846e08d9c838f9e866a1bb4a66a2fd3ba3c9e7da3cf9e394dfd7'
VESTED = '0xfbeff59d2bfda0d79ea8a29f8c57c66d48c7a13eabbdb90908d9115ec41c9dc6'
BORROW = '0x13ed6866d4e1ee6da46f845c46d7e54120883d75c5ea9a2dacc1c4ca8984ab80'
XFLOBBYEXIT = '0xa6b19fa7f41317a186e1d58e9d81f86a52f1102b6bce10b4eca83f37aaa58468'

ADDR_UNISWAP_AIRDROP = '0x090D4613473dEE047c3f2706764f49E0821D256e'
ADDR_MIRROR_AIRDROP = '0x2A398bBa1236890fb6e9698A698A393Bb8ee8674'
ADDR_PIEDAO_INCENTIVES = (
    '0x8314337d2b13e1A61EadF0FD1686b2134D43762F'.lower(),
    '0xb9a4bca06f14a982fcd14907d31dfacadc8ff88e',
    '0xb8e59ce1359d80e4834228edd6a3f560e7534438'
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
ADDR_MIR_REWARDS = '0x5d447Fc0F8965cED158BAB42414Af10139Edf0AF'
ADDR_XTOKEN_AIRDROP = '0x11f10378fc56277eEdBc0c3309c457b0fd5c6dfd'
ADDR_SWERVE_MINTER = '0x2c988c3974ad7e604e276ae0294a7228def67974'
ADDR_FEI_GENESIS_GROUP = '0xBFfB152b9392e38CdDc275D818a3Db7FE364596b'
ADDR_DODO_REWARDS = '0x0e504d3e053885a82bd1cb5c29cbaae5b3673be4'
ADDR_IMX_AIRDROP = '0x2011b5d4d5287cc9d3462b4e8af0e4daf29e3c1d'
ADDR_ROOK_REWARDS = '0x2777b798fdfb906d42b89cf8f9de541db05dd6a1'
ADDR_SUSHI_REWARDS = '0xc2edad668740f1aa35e4d8f227fb8e17dca888cd'
ADDR_GITCOIN_AIRDROP = '0xde3e5a990bce7fc60a6f017e7c4a95fc4939299e'
ADDR_BLACKPOOL_AIRDROP = '0x6b63564a8b3f145b3ef085bcc197c0ff64e9a140'
ADDR_TORN_VTORN = '0x3eFA30704D2b8BBAc821307230376556cF8CC39e'
ADDR_XTK_VESTING = '0x2ac34f8327aceD80CFC04085972Ee06Be72A45bb'
ADDR_FOX_AIRDROP = '0xd1Fa5AA6AD65eD6FEA863c2e7fB91e731DcD559F'
ADDR_FOX_AIRDROP_2 = '0x91B9A78658273913bf3F5444Cb5F2592d1123eA7'
ADDR_FOX_AIRDROP_3 = '0xf4BBE639CCEd35210dA2018b0A31f4E1449B2a8a'
ADDR_FOX_AIRDROP_4 = '0x7BC08798465B8475Db9BCA781C2Fd6063A09320D'
ADDR_UMA_TVL_OPT = '0x0Ee5Bb3dEAe8a44FbDeB269941f735793F8312Ef'

ADDR_DODO = '0x43Dfc4159D86F3A37A5A4B3D4580b888ad7d4DDd'
ADDR_SUSHI = '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2'
ADDR_TORN = '0x77777feddddffc19ff86db637967013e6c6a116c'
ADDR_HEX = '0x2b591e99afE9f32eAA6214f7B7629768c40Eeb39'
ADDR_COMPOUND_DAI = '0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643'
ADDR_DAI = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
ADDR_BADGER = '0x3472A5A71965499acd81997a54BBA8D852C6E53d'
ADDR_UMA = '0x04Fa0d235C4abf4BcF4787aF4CF447DE572eF828'


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

        elif event['topics'][0] == CLAIMED and event['address'] == ADDR_IMX_AIRDROP.lower():
            amount = hexstr_to_int(event['data'][130:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0x7b35ce522cb72e4077baeb96cb923a5529764a00'),
                notes='IMX airdrop',
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

        elif event['topics'][0] == CLAIMED_2 and event['address'] == ADDR_ROOK_REWARDS.lower():
            amount = hexstr_to_int(event['data'][2:])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.INCOME,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('ROOK'),
                notes='Rook rewards for providing liquidity',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED_2:
            logger.warning('Unknown Claimed event for tx: %s', tx_hash)

        if event['topics'][0] == CLAIMED_4 and event['address'] == ADDR_GITCOIN_AIRDROP.lower():
            amount = hexstr_to_int(event['data'][2:][128:192])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0xDe30da39c46104798bB5aA3fe8B9e0e1F348163F'),
                notes='Gitcoin retroactive airdrop',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED_4:
            logger.warning('Unknown Claimed event for tx: %s', tx_hash)

        if event['topics'][0] == CLAIMED_5 and event['address'] in (
                ADDR_FOX_AIRDROP.lower(),
                ADDR_FOX_AIRDROP_2.lower(),
                ADDR_FOX_AIRDROP_3.lower(),
                ADDR_FOX_AIRDROP_4.lower()
                ):
            amount = hexstr_to_int(event['data'][2:][64:128])
            actions += [LedgerAction(
                identifier=None,
                location='',
                action_type=LedgerActionType.AIRDROP,
                amount=FVal(amount) / FVal(1e18),
                rate=None,
                rate_asset=None,
                timestamp=txn.timestamp,
                asset=symbol_to_asset_or_token('_ceth_0xc770EEfAd204B5180dF6a14Ee197D99d808ee52d'),
                notes='FOX token airdrop',
                link=tx_hash
            )]

        elif event['topics'][0] == CLAIMED_5:
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

        elif event['topics'][0] == TRANSFER and event['address'] == ADDR_SUSHI.lower():
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(ADDR_SUSHI_REWARDS) and \
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
                    asset=symbol_to_asset_or_token('SUSHI'),
                    notes='Claim SUSHI rewards for staking LP',
                    link=tx_hash
                )]

        elif event['topics'][0] == TRANSFER and event['address'] == ADDR_TORN.lower():
            asset = symbol_to_asset_or_token('_ceth_0x77777FeDdddFfC19Ff86DB637967013e6C6A116C')
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(ADDR_TORN_VTORN) and \
                    hexstr_to_int(event['topics'][2]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.AIRDROP,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=asset,
                    notes='TORN airdrop',
                    link=tx_hash
                )]

        elif event['topics'][0] == TRANSFER and event['address'] == ADDR_DAI.lower():
            # MakerDAO Mint
            # Until we clarify generalized lending support in Buchfink,
            # treat borrowed DAI as a gift you have to pay back
            asset = symbol_to_asset_or_token('DAI')
            if hexstr_to_int(event['topics'][1]) == 0 and \
                    hexstr_to_int(event['topics'][2]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.GIFT,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=asset,
                    notes='DAI mint',
                    link=tx_hash
                )]

        elif event['topics'][0] == TRANSFER and event['address'] == ADDR_UMA.lower():
            # UMA TVL Option Settlement
            asset = symbol_to_asset_or_token('_ceth_' + ADDR_UMA)
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(ADDR_UMA_TVL_OPT) and \
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
                    asset=asset,
                    notes='UMA TVL option settlement',
                    link=tx_hash
                )]

        if event['topics'][0] == STAKEEND and event['address'] == ADDR_HEX.lower():
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(account.address):
                payout = hexstr_to_int(event['data'][2:][:18])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.INCOME,
                    amount=FVal(payout) / FVal(1e8),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=symbol_to_asset_or_token('_ceth_' + ADDR_HEX),
                    notes='HEX Payout for staking',
                    link=tx_hash
                )]

        if event['topics'][0] == HUNT and event['address'] == ADDR_BLACKPOOL_AIRDROP.lower():
            asset = symbol_to_asset_or_token('_ceth_0x0eC9F76202a7061eB9b3a7D6B59D36215A7e37da')
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'][2:][64:128])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.AIRDROP,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=asset,
                    notes='Blackpool airdrop',
                    link=tx_hash
                )]

        if event['topics'][0] == VESTED and event['address'] == ADDR_XTK_VESTING.lower():
            asset = symbol_to_asset_or_token('_ceth_0x7F3EDcdD180Dbe4819Bd98FeE8929b5cEdB3AdEB')
            if hexstr_to_int(event['topics'][1]) == hexstr_to_int(account.address):
                amount = hexstr_to_int(event['data'][2:][64:128])
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.INCOME,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=asset,
                    notes='XTK Rewards for LP staking',
                    link=tx_hash
                )]

        # Until we clarify generalized lending support in Buchfink,
        # treat borrowed DAI as a gift you have to pay back
        if event['topics'][0] == BORROW and event['address'] == ADDR_COMPOUND_DAI.lower():
            asset = symbol_to_asset_or_token('DAI')
            borrower = hexstr_to_int(event['data'][2:][:64])
            amount = hexstr_to_int(event['data'][2:][64:128])
            if borrower == hexstr_to_int(account.address):
                actions += [LedgerAction(
                    identifier=None,
                    location='',
                    action_type=LedgerActionType.GIFT,
                    amount=FVal(amount) / FVal(1e18),
                    rate=None,
                    rate_asset=None,
                    timestamp=txn.timestamp,
                    asset=asset,
                    notes='Compound DAI mint',
                    link=tx_hash
                )]

        if event['topics'][0] == XFLOBBYEXIT and event['address'] == ADDR_HEX.lower():
            asset = symbol_to_asset_or_token('_ceth_' + ADDR_HEX)

            # Find another TRANSFER
            for ev2 in receipt['logs']:
                if ev2['topics'][0] == TRANSFER and \
                        ev2['address'] == ADDR_HEX.lower() and \
                        hexstr_to_int(ev2['topics'][1]) == 0 and \
                        hexstr_to_int(ev2['topics'][2]) == hexstr_to_int(account.address):

                    amount = hexstr_to_int(ev2['data'][2:])
                    # We will classify those as GIFT instead of purche because
                    # we already paid earlier
                    actions += [LedgerAction(
                        identifier=None,
                        location='',
                        action_type=LedgerActionType.GIFT,
                        amount=FVal(amount) / FVal(1e8),
                        rate=None,
                        rate_asset=None,
                        timestamp=txn.timestamp,
                        asset=asset,
                        notes='XFLOBBYEXIT HEX mint',
                        link=tx_hash
                    )]
    return actions
