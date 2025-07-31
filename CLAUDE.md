# Buchfink Project - Claude Code Documentation

## Project Overview

Buchfink is a Python project that extends and builds upon the [rotki](https://rotki.com/) codebase. Rotki is an open-source portfolio tracking, analytics, accounting and tax reporting application for cryptocurrencies.

## Relationship to Rotki

Buchfink imports and uses many components from the rotki codebase located at `../rotki/`. It appears to be a specialized reporting and analysis tool that leverages rotki's:
- Database handling capabilities
- Asset management systems
- Blockchain transaction processing
- Exchange integrations
- Accounting structures

## Current Development Status

The project is currently being updated to work with the latest rotki develop branch, which has undergone significant API changes including:

### Major API Changes from Rotki
1. **Trade structures**: `Trade` and `TradeType` classes have been replaced by `HistoryEvent` and `EventDirection`
2. **Import paths**: Many modules have been reorganized (e.g., `accounting.structures.types` → `accounting.types`)
3. **Etherscan integration**: Moved from `chain.ethereum.etherscan` to `externalapis.etherscan`
4. **Asset updates**: `globaldb.updates` → `globaldb.asset_updates.manager`
5. **Balance structures**: Constructor parameters changed from `balance` to `amount`

## Rotki Codebase Structure

### Key Directories:
- `rotkehlchen/accounting/` - Accounting logic, PnL calculations, cost basis tracking
- `rotkehlchen/assets/` - Asset management, resolution, spam detection
- `rotkehlchen/chain/` - Blockchain-specific modules (Ethereum, Bitcoin, etc.)
  - `ethereum/modules/` - DeFi protocol integrations (Uniswap, Aave, etc.)
- `rotkehlchen/db/` - Database handling, schema, migrations
- `rotkehlchen/exchanges/` - Exchange integrations (Kraken, Binance, etc.)
- `rotkehlchen/externalapis/` - External API integrations (Etherscan, CoinGecko, etc.)
- `rotkehlchen/globaldb/` - Global asset database management
- `rotkehlchen/history/` - Historical data processing, events, price tracking
- `rotkehlchen/types.py` - Core type definitions

### History Events System
Rotki has moved to a unified history events system:
- `HistoryEvent` - Base class for all financial events
- `HistoryEventType` - Categories like TRADE, DEPOSIT, WITHDRAWAL, etc.
- `HistoryEventSubType` - Subcategories like FEE, REWARD, etc.
- `EventDirection` - IN, OUT, NEUTRAL (replaces TradeType.BUY/SELL)

### Important Files in Buchfink:
- `buchfink/db.py` - Database interface extending rotki's DBHandler
- `buchfink/datatypes.py` - Type imports and compatibility layer
- `buchfink/serialization.py` - Data serialization utilities
- `buchfink/classification.py` - Transaction classification logic
- `buchfink/report.py` - Report generation

## Development Notes

- Always check `../rotki/` for the current API structure
- Import errors usually indicate moved modules in rotki
- Run "make" to validate any changes
