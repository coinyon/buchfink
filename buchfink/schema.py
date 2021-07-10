from voluptuous import Any, Required, Schema

FetchConfig = Schema({
    'trades': bool,  # default: true
    'actions': bool,  # default: true
    'balances': bool  # default: true
})

exchange_account = Schema({
    Required('name'): str,
    Required('exchange'): str,
    Required('api_key'): str,
    Required('secret'): str,
    'passphrase': str,
    'fetch': FetchConfig
})

ethereum_account = Schema({
    Required('name'): str,
    Required('ethereum'): str,
    'fetch': FetchConfig
})

bitcoin_account = Schema({
    Required('name'): str,
    Required('bitcoin'): str,
    'fetch': FetchConfig
})

manual_account = Schema({
    Required('name'): str,
    Required('file'): str,
    'fetch': FetchConfig
})

report_schema = Schema({
    Required('name'): str,
    Required('from'): str,
    Required('to'): str,
    'title': str,
    'template': str
})

settings_schema = Schema({
    'main_currency': str,
    'taxfree_after_period': int,
    'include_gas_costs': bool,
    'include_crypto2crypto': bool,
    'external_services': {
        'etherscan': Any(None, str),
        'cryptocompare': Any(None, str)
    }
})

token_or_asset = Schema({
    'type': str,
    'name': str,
    'address': str,
    'symbol': str,
    'decimals': int,
    'coingecko': Any(None, str),
    'cryptocompare': Any(None, str)
})

config_schema = Schema({
    Required('accounts'): [Any(
        exchange_account,
        ethereum_account,
        bitcoin_account,
        manual_account
    )],
    'tokens': [token_or_asset],
    'reports': [report_schema],
    'settings': settings_schema
})
