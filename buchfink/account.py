from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from rotkehlchen.typing import ChecksumEthAddress
from typing_extensions import Literal


@dataclass
class Account:
    name: str
    account_type: Union[Literal["ethereum"], Literal["bitcoin"]]
    address: Optional[Union[ChecksumEthAddress, str]]
    config: Dict[str, Any]


def account_from_config(config_account):
    if 'ethereum' in config_account:
        account_type = "ethereum"
        address = config_account["ethereum"]
    elif 'bitcoin' in config_account:
        account_type = "bitcoin"
        address = config_account["bitcoin"]
    elif 'exchange' in config_account:
        account_type = "exchange"
        address = None
    elif 'file' in config_account:
        account_type = "file"
        address = None
    else:
        raise ValueError("Invalid account")
    return Account(
        name=config_account["name"],
        account_type=account_type,
        address=address,
        config=config_account
    )


def accounts_from_config(config) -> List[Account]:
    return [account_from_config(acc) for acc in config['accounts']]


def account_from_string(acc_def: str, db) -> Account:
    if acc_def.lower().endswith('.eth'):
        eth_address = db.ethereum_manager.ens_lookup(acc_def)
        if not eth_address:
            raise ValueError(f'Could not resolve ENS: {acc_def}')
        return Account(acc_def, 'ethereum', eth_address, {})

    if acc_def.lower().startswith('0x'):
        return Account(acc_def, 'ethereum', acc_def, {})

    raise ValueError(acc_def)
