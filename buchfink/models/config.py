from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


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
    tags: List[str] = []


class EthereumAccountConfig(BaseModel):
    name: str
    ethereum: str
    fetch: Optional[FetchConfig] = None
    tags: List[str] = []


class BitcoinAccountConfig(BaseModel):
    name: str
    bitcoin: str
    fetch: Optional[FetchConfig] = None
    tags: List[str] = []


class BitcoinCashAccountConfig(BaseModel):
    name: str
    bitcoincash: str
    fetch: Optional[FetchConfig] = None
    tags: List[str] = []


class GenericAccountConfig(BaseModel):
    name: str
    fetch: Optional[FetchConfig] = None
    tags: List[str] = []


AccountConfig = Union[
    ExchangeAccountConfig,
    EthereumAccountConfig,
    BitcoinAccountConfig,
    BitcoinCashAccountConfig,
    GenericAccountConfig,
]


class ReportConfigFromConfigFile(BaseModel):
    name: str
    from_: str = Field(alias='from')
    to: str
    title: Optional[str] = None
    template: Optional[str] = None
    limit_accounts: List[str] = []
    exclude_accounts: List[str] = []
    active: bool = True


class ExternalServicesConfig(BaseModel):
    etherscan: Optional[str] = None
    cryptocompare: Optional[str] = None
    loopring: Optional[str] = None
    beaconchain: Optional[str] = None
    opensea: Optional[str] = None
    blockscout: Optional[str] = None
    coingecko: Optional[str] = None
    defillama: Optional[str] = None


class RpcNode(BaseModel):
    name: str
    endpoint: str


class Settings(BaseModel):
    main_currency: Optional[str] = None
    taxfree_after_period: Optional[int] = None
    include_gas_costs: Optional[bool] = None
    include_crypto2crypto: Optional[bool] = None
    external_services: Optional[ExternalServicesConfig] = None
    rpc_nodes: Optional[List[RpcNode]] = None
    ignored_assets: List[str] = []
    ksm_rpc_endpoint: str = ''
    dot_rpc_endpoint: str = ''


class AssetConfig(BaseModel):
    type: Optional[str]
    name: Optional[str]
    address: Optional[str]
    symbol: Optional[str]
    decimals: Optional[int]
    chain_id: Optional[int] = None
    coingecko: Optional[str] = None
    cryptocompare: Optional[str] = None


class HistoricalPriceConfig(BaseModel):
    from_: str = Field(alias='from')
    to: str
    at: datetime
    price: Optional[float]


class Config(BaseModel):
    accounts: List[AccountConfig] = []
    tokens: List[AssetConfig] = []
    reports: List[ReportConfigFromConfigFile] = []
    prices: List[HistoricalPriceConfig] = []
    settings: Settings


class ReportConfig(BaseModel):
    name: str
    title: Optional[str] = None
    template: Optional[str] = None
    from_dt: datetime
    to_dt: datetime
    limit_accounts: List[str] = []
    exclude_accounts: List[str] = []
    active: Optional[bool] = True

    @staticmethod
    def from_config(report: ReportConfigFromConfigFile) -> 'ReportConfig':
        return ReportConfig(
            name=str(report.name),
            title=report.title,
            template=report.template,
            from_dt=datetime.fromisoformat(str(report.from_)),
            to_dt=datetime.fromisoformat(str(report.to)),
            limit_accounts=report.limit_accounts,
            exclude_accounts=report.exclude_accounts,
            active=report.active,
        )
