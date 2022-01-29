from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel


class FetchConfig(BaseModel):
    trades: Optional[bool] = True
    actions: Optional[bool] = True
    balances: Optional[bool] = True


class ExchangeAccountConfig(BaseModel):
    name: str
    exchange: str
    api_key: str
    secret: str
    passphrase: Optional[str] = None
    fetch: Optional[FetchConfig] = None
    tags: Optional[List[str]]


class EthereumAccountConfig(BaseModel):
    name: str
    ethereum: str
    fetch: Optional[FetchConfig] = None
    tags: Optional[List[str]]


class BitcoinAccountConfig(BaseModel):
    name: str
    bitcoin: str
    fetch: Optional[FetchConfig] = None
    tags: Optional[List[str]]


class ManualAccountConfig(BaseModel):
    name: str
    file: str
    fetch: Optional[FetchConfig] = None
    tags: Optional[List[str]]


AccountConfig = Union[
        ExchangeAccountConfig,
        EthereumAccountConfig,
        BitcoinAccountConfig,
        ManualAccountConfig
    ]


class ReportConfig2(BaseModel):
    name: str
    from_: str
    to: str
    title: Optional[str]
    template: Optional[str]

    class Config:
        fields = {
            'from_': 'from'
        }


class ExternalServicesConfig(BaseModel):
    etherscan: Optional[str]
    cryptocompare: Optional[str]
    loopring: Optional[str]
    beaconchain: Optional[str]
    opensea: Optional[str]


class Settings(BaseModel):
    main_currency: Optional[str]
    taxfree_after_period: Optional[int]
    include_gas_costs: Optional[bool]
    include_crypto2crypto: Optional[bool]
    external_services: Optional[ExternalServicesConfig]
    eth_rpc_endpoint: Optional[str]


class AssetConfig(BaseModel):
    type: Optional[str]
    name: Optional[str]
    address: Optional[str]
    symbol: Optional[str]
    decimals: Optional[int]
    coingecko: Optional[str] = None
    cryptocompare: Optional[str] = None


class HistoricalPriceConfig(BaseModel):
    from_: str
    to: str
    at: datetime
    price: Optional[float]

    class Config:
        fields = {
            'from_': 'from'
        }


class Config(BaseModel):
    accounts: List[AccountConfig] = []
    tokens: List[AssetConfig] = []
    reports: List[ReportConfig2] = []
    prices: List[HistoricalPriceConfig] = []
    settings: Settings


class ReportConfig(BaseModel):
    name: str
    title: Optional[str]
    template: Optional[str]
    from_dt: datetime
    to_dt: datetime
