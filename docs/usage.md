# Usage

Create a new directory where you want to store your data and initialize Buchfink:

    buchfink init

This will create a `buchfink.yaml` that you can edit to fit your needs. A good
first start would be to add your accounts and set some general accounting
settings like the main currency. See [Configuration](./configuration.md) for more
information.

## Retrieve data

Update your local files by running:

    buchfink fetch

This will go through all your configured accounts and gets the trades and
balances.

## Check balances

You can then check your balances by running:

    buchfink balances

## Tax reports

You can generate an ad-hoc tax report like this:

    buchfink report --year 2022

You can also declare reports in your `buchfink.yaml`.

Buchfink also allows you to print out the "tax-free allowances", i.e. the
amounts of each asset that you are able to sell tax-free at this point in time:

    buchfink allowances

Of course, this only applies to a jurisdiction where crypto assets are tax-free
after a certain period.
