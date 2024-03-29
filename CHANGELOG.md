# Changelog

## master

* Support specification of ignored assets via setting

## 0.0.15

* Ethereum gas spent will be decoded and store in YAML as actions

## 0.0.14

* Can print QR code for blockchain accounts (buchfink list -o qrcode)
* Can use own web3 nodes for blockchain queries
* Support Bitcoin Cash

## 0.0.13

* Add NFT support
* Ability to rerender report template without running report
* Add Ethereum gas costs to tax reports
* Requires Python 3.9 now due to upstream dependency

## 0.0.12

* Add --type/t flag to "actions" subcommand
* Add fiat amount value to "actions" subcommand
* Can give path to config file via option and environment variable
* Support automatic detection of SushiSwap trades

## 0.0.11

* Can set a list of tags per account

## 0.0.10

* New "actions" command to show ledger actions
* Can turn off fetching of trades, balances or actions per account
* "quote" subcommand now has a timestamp (-t) option to query historical prices
* "cache" subcommand to build a historical prices cache
* Can add manual historic prices to yaml

## 0.0.9

* Add ability to add custom tokens to yaml
* Ambiguous symbols are now serialized as 'SYMBOL[UNIQUE_IDENTIFIER]'
* Add new "quote" subcommnad
* Balances will now show "small balances" in sum and table

## 0.0.8

* Balances will now be serialized sorted by asset
* init will also create .gitignore
* Support ENS domains for "ad-hoc accounts"

## 0.0.7

* Add classification of Ethereum transactions to ledger actions
* Support "ledger actions" such an income, airdrop, loss...

## 0.0.6

* Add "buchfink trades" command to list/filter trades
* "buchfink balances" will now save balances to local files
* Allow cryptocompare API key credential

## 0.0.5

* Can also show liabilities for certain Ethereum protocols
* Can fetch uniswap trades
* Add "buchfink list" command

## 0.0.4

* Add ability to add credentials for external services like Etherscan
* Balances are now shown in configured fiat value, not always USD
* Reports can be rendered with jinja2 templates (to HTML, CSV or similar)
* Manual file-based accounts can now also contain balances for any asset
* New table output with better number formatting
* Bugfix: Fiat currency setting was not correctly used in reports

## 0.0.3

* Balances will now also show BTC, ETH and ERC20 blockchain balances
* Add `allowances` command to show the assets that can be sold tax-free
