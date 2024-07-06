# Configuration

## Account configuration

### Blockchain accounts

To add your blockchain accounts, simply add them to your `buchfink.yaml`:

```yaml
accounts:
  - name: donation-address
    ethereum: '0xFa2C0AbdaeDc8099887914Ab25AD11B3846655B9'

  - name: random-btc-address
    bitcoin: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'

  ...
```

The following blockchains are supported:

  * Ethreum (`ethereum: 0xADDRESS`)
  * Bitcoin (`bitcoin: ADDRESS`)
  * Bitcoin Cash (`bitcoincash: ADDRESS`)

Buchfink is able to fetch the account balances for blockchain accounts and
also supports a variety of Ethereum protocols (see Rotki for more information).
On-chain trades are also supported for some protocols (e.g. Uniswap).

### Exchange accounts

Accounts for crypto exchanges can be added to your `buchfink.yaml` like this:

```yaml
accounts:
  - name: my-kraken-account
    exchange: kraken
    api_key: ...
    secret: ...
```

You can add multiple accounts for each exchange. Buchfink supports all
exchanges that Rotki supports, namely:

  * binance
  * bitcoinde (Bitcoin.de)
  * bitmex
  * bittrex
  * coinbase
  * gemini
  * iconomi
  * kraken
  * poloniex

If your exchange is not supported yet, see the section "Add manual accounts"
below and add your data manually.

### Manual accounts

Adding manual accounts is easy, just create a new YAML file containing your
trades (and/or balances) and at this to your `buchfink.yaml`.

```yaml
accounts:
  - name: otc
    file: accounts/otc.yaml
```

The file `accounts/otc.yaml` may look like this:

```yaml
trades:
- buy: 1 BTC
  for: 1000 USD
  link: '1'
  timestamp: '2017-01-15T19:49:27'
- sell: 1 BTC
  for: 16000 USD
  link: '2'
  timestamp: '2017-11-15T19:51:26'
```

Note: This is exactly the same serialization format that the `fetch` command
generates for your exchanges trades. So you can easily amend missing trades by
copy and pasting and changing the relevant lines.

The manual account YAML file can also contain assets or liablities that will be
respected by the `buchfink balances` command:

```yaml
assets:
- amount: 0.5
  asset: ETH
- amount: 10
  asset: KNC
liablities:
- amount: 100
  asset: DAI
```

## Settings

Global settings can be configured in `buchfink.yaml` in the `settings` section:

```yaml
settings:

  # The base currency that is used for accounting and reports
  main_currency: USD

  # Seconds after which an asset can be sold tax-free
  taxfree_after_period: 31536000
```
