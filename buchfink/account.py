from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union

from rotkehlchen.typing import ChecksumEthAddress


@dataclass
class Account:
    name: str
    account_type: Union[Literal["ethereum"]]
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
    return Account(name=config_account["name"], account_type=account_type, address=address, config=config_account)


def accounts_from_config(config):
    return [account_from_config(acc) for acc in config['accounts']]
