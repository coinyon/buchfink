Buchfink - Plain Crypto Taxes
=============================

Under the hood, Buchfink uses algorithms and data structures from Rotki, the
open source portfolio tracker. But instead of a GUI, local accounts and an
encrypted database, Buchfink uses the CLI and plain text files for
configuration and trade storage.

## Usage

Create a new directory where you want to store your data and initialize Buchfink:

  buchfink init

Then, edit `buchfink.yaml` to fit your needs. You can add exchange API keys and change accounting settings like the main currency.

After that, run the following command to retrieve all your trades from the exchange API:

  buchfink fetch

Then you can generate your tax report with:

  buchfink report --from=2019-01-01 --to=2019-31-01

## Configuration

### Add exchange accounts

...

### Add manual trades

...
