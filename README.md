# Buchfink - Plaintext Crypto Portfolio

<p align="center">
  <img width="460" src="./docs/buchfink_logo.png" />

  ![Tests](https://github.com/coinyon/buchfink/actions/workflows/ci.yml/badge.svg)
</p>

Buchfink is a commandline application that you can use for performing book-keeping over
your crypto trades and generate profit/loss statements and tax reports.

Under the hood, Buchfink uses algorithms and data structures from
[rotki](https://github.com/rotki/rotki), the open source portfolio tracker. But
instead of a GUI, user accounts and an encrypted database, Buchfink uses a
CLI and plain text files for declarative configuration and storage.

Note: Buchfink is early alpha. Do NOT use it for tax or trading purposes.
But feel free to report bugs and missing features.

## Architecture

![Buchfink Architecture](./Architecture.svg)

## Documentation

* [Installation](docs/installation.md)
* [Usage](docs/usage.md)
* [Configuration](docs/configuration.md)

## Donation

If you find this useful and want to contribute to further development, consider an
ETH or ERC-20 donation at [coinyon.eth](https://etherscan.io/address/coinyon.eth).

I also encourage you to try out and support
[rotki](https://github.com/rotki/rotki). Buchfink would not be possible without it.
