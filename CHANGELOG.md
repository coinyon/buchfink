master
------

* Add "buchfink trades" command to list/filter trades
* "buchfink balances" will now save balances to local file

0.0.5
------

* Can also show liabilities for certain Ethereum protocols
* Can fetch uniswap trades
* Add "buchfink list" command

0.0.4
-----

* Add ability to add credentials for external services like Etherscan
* Balances are now shown in configured fiat value, not always USD
* Reports can be rendered with jinja2 templates (to HTML, CSV or similar)
* Manual file-based accounts can now also contain balances for any asset
* New table output with better number formatting
* Bugfix: Fiat currency setting was not correctly used in reports

0.0.3
-----

* Balances will now also show BTC, ETH and ERC20 blockchain balances
* Add `allowances` command to show the assets that can be sold tax-free
