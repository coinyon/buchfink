Buchfink - Plaintext Crypto Taxes
=================================

Buchfink is a commandline application that you can use for keeping book over
your crypto trades and generate profit/loss statements and tax reports.

Under the hood, Buchfink uses algorithms and data structures from
[Rotki](https://github.com/rotki/rotki), the open source portfolio tracker. But
instead of a GUI, user accounts and an encrypted database, Buchfink uses the
CLI and plain text files for declarative configuration and trade storage.

Note: Buchfink is early alpha. Do NOT use it for tax or trading purposes.
But feel free to report bugs and missing features.

## Installation

Install Buchfink like this (you may want to create a virtualenv):

    pip install git+https://github.com/coinyon/buchfink.git

## Usage

Create a new directory where you want to store your data and initialize Buchfink:

    buchfink init

Then, edit `buchfink.yaml` to fit your needs. You can add your accounts (see
below) and change accounting settings like the main currency.

You can then check your balances by running:

    buchfink balances

In order to prepare your tax or profit/loss report, you need to to retrieve your
individual trades. Do this by running:

    buchfink fetch

Then you can generate your tax report with:

    buchfink report -n my_tax_2019 --from=2019-01-01 --to=2020-01-01

## Configuration

### Add exchange accounts

Just add the account to your `buchfink.yaml` like this:

```yaml
accounts:
  - name: kraken1
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
  * coinbasepro
  * gemini
  * iconomi
  * kraken
  * poloniex

### Adding blockchain accounts

To add your Ethereum and Bitcoin blockchain accounts, add them to your
`buchfink.yaml` as well:

```yaml
accounts:
  - name: donation-address
    ethereum: 0xFa2C0AbdaeDc8099887914Ab25AD11B3846655B9

  - name: random-btc-address
    bitcoin: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
  ...
```

Note: Currently, Buchfink and Rotki will not yet fetch your DEX trades, but
they will be able to in the future.

### Add manual trades

Adding manual trades is easy, just create a new YAML file containing your
trades and at this to your `buchfink.yaml`.

```yaml
accounts:
  - name: otc
    file: otc.yaml
```

The file `otc.yaml` may look like this:

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

## Donation

If you find this useful and want to contribute to further development, consider an
ETH or ERC-20 donation at [coinyon.eth](https://etherscan.io/address/coinyon.eth).

I also encourage you to try out and support
[Rotki](https://github.com/rotki/rotki). Buchfink would not be possible without it.
