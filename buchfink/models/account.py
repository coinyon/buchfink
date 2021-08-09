from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from rotkehlchen.typing import ChecksumEthAddress
from typing_extensions import Literal

from .config import (AccountConfig, BitcoinAccountConfig, Config,
                     EthereumAccountConfig, ExchangeAccountConfig,
                     ManualAccountConfig)

AccountType = Union[Literal["ethereum"], Literal["bitcoin"], Literal["exchange"], Literal["file"]]


class Account(BaseModel):
    name: str
    account_type: AccountType
    address: Optional[Union[ChecksumEthAddress, str]]
    config: AccountConfig


def account_from_config(account_config: AccountConfig):
    account_type = "ethereum"   # type: AccountType
    if isinstance(account_config, EthereumAccountConfig):
        account_type = "ethereum"
        address = account_config.ethereum
    elif isinstance(account_config, BitcoinAccountConfig):
        account_type = "bitcoin"
        address = account_config.bitcoin
    elif isinstance(account_config, ExchangeAccountConfig):
        account_type = "exchange"
        address = None
    elif isinstance(account_config, ManualAccountConfig):
        account_type = "file"
        address = None
    else:
        raise ValueError("Invalid account")
    return Account(
        name=account_config.name,
        account_type=account_type,
        address=address,
        config=account_config
    )


def accounts_from_config(config: Config) -> List[Account]:
    return [account_from_config(acc) for acc in config.accounts]


def account_from_string(acc_def: str, buchfink_db) -> Account:
    if acc_def.lower().endswith('.eth'):
        eth_address = buchfink_db.ethereum_manager.ens_lookup(acc_def)
        if not eth_address:
            raise ValueError(f'Could not resolve ENS: {acc_def}')
        return Account(acc_def, 'ethereum', eth_address, {})

    if acc_def.lower().startswith('0x'):
        return Account(acc_def, 'ethereum', acc_def, {})

    raise ValueError(acc_def)
