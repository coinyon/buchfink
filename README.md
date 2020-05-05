Buchfink - Plain Crypto Taxes
=============================

Buchfink is a commandline application that you can use for keeping book over
your crypto trades and generate profit/loss statements and tax reports.

Under the hood, Buchfink uses algorithms and data structures from Rotki, the
open source portfolio tracker. But instead of a GUI, user accounts and an
encrypted database, Buchfink uses the CLI and plain text files for
configuration and trade storage.

## Usage

Create a new directory where you want to store your data and initialize Buchfink:

    buchfink init

Then, edit `buchfink.yaml` to fit your needs. You can add exchange API keys and
change accounting settings like the main currency.

After that, run the following command to retrieve all your trades from the
exchange API:

    buchfink fetch

Then you can generate your tax report with:

    buchfink report --from=2019-01-01 --to=2019-31-01

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

You can add multiple accounts for each exchange. Buchfink supports all exchanges that Rotki supports, namely:

  * kraken
  * coinbase
  * poloniex
  * gemini
  * bitmex
  * bittrex
  * coinbasepro

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

### Add manual trades

Adding manual trades is easy, just create a new YAML file containing your
trades and at this to your `buchfink.yaml`.

```yaml
accounts:
  - name: otc
    file: otc.yaml
```

otc.yaml:

```yaml
trades:
- buy: 1 BTC
  for: 1000 USD
  fee: 0 USD
  link: '1'
  timestamp: '2017-01-15T19:49:27'
- sell: 1 BTC
  for: 16000 USD
  fee: 0 USD
  link: '2'
  timestamp: '2017-11-15T19:51:26'
```
