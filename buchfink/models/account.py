from typing import List, Optional, Union

from pydantic import BaseModel
from rotkehlchen.types import ChecksumEvmAddress
from typing_extensions import Literal

from .config import (
    AccountConfig,
    BitcoinAccountConfig,
    BitcoinCashAccountConfig,
    Config,
    EthereumAccountConfig,
    ExchangeAccountConfig,
    ManualAccountConfig
)

AccountType = Union[
    Literal["ethereum"],
    Literal["bitcoin"],
    Literal["bitcoincash"],
    Literal["exchange"],
    Literal["file"]
]


class Account(BaseModel):
    name: str
    account_type: AccountType
    address: Optional[Union[ChecksumEvmAddress, str]]
    tags: List[str] = []
    config: AccountConfig


def account_from_config(account_config: AccountConfig):
    account_type = "ethereum"   # type: AccountType
    address = None  # type: Optional[str]
    if isinstance(account_config, EthereumAccountConfig):
        account_type = "ethereum"
        address = account_config.ethereum
    elif isinstance(account_config, BitcoinAccountConfig):
        account_type = "bitcoin"
        address = account_config.bitcoin
    elif isinstance(account_config, BitcoinCashAccountConfig):
        account_type = "bitcoincash"
        address = account_config.bitcoincash
    elif isinstance(account_config, ExchangeAccountConfig):
        account_type = "exchange"
    elif isinstance(account_config, ManualAccountConfig):
        account_type = "file"
    else:
        raise ValueError("Invalid account")
    return Account(
        name=account_config.name,
        account_type=account_type,
        address=address,
        config=account_config,
        tags=account_config.tags or []
    )


def accounts_from_config(config: Config) -> List[Account]:
    return [account_from_config(acc) for acc in config.accounts]


def account_from_string(acc_def: str, buchfink_db=None) -> Account:
    if acc_def.lower().endswith('.eth'):
        if buchfink_db is None:
            raise ValueError('DB is required to resolve ENS name')

        eth_address = buchfink_db.ethereum_inquirer.ens_lookup(acc_def)
        if not eth_address:
            raise ValueError(f'Could not resolve ENS: {acc_def}')

        config = {
            'name': acc_def,
            'ethereum': eth_address,
        }
        return Account(
                name=acc_def,
                account_type='ethereum',
                address=eth_address,
                config=config,
                tags=[]
            )

    if acc_def.lower().startswith('0x'):
        config = {
            'name': acc_def,
            'ethereum': acc_def,
        }
        return Account(
                name=acc_def,
                account_type='ethereum',
                address=acc_def,
                config=config,
                tags=[]
            )

    raise ValueError(acc_def)
