# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pycgt is a capital gain tax calculator for crypto traders/investors, specifically designed for Australian tax returns. It processes CSV files containing trading transaction logs and generates annual tax statements with capital gains/losses calculations.

## Environment Setup

```bash
python3 -m venv .virtualenv
source .virtualenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py [csv_files...]
```

Example:

```bash
python main.py example.csv
python main.py "BtcTax2018 - July2013-June2014.csv" "BtcTax2018 - July2014-June2015.csv"
```

The application outputs CSV-formatted gain/loss records to stdout, followed by annual tax summaries. You can redirect output to a file if needed:

```bash
python main.py example.csv > results.csv
```

## Configuration

All settings are centralized in `config.toml`:

- **[locale]**: Fiat currency (default: aud) and fiscal year start month (default: 7 for July)
- **[options]**: Position accounting method (filo/fifo), datetime sorting, precision threshold for floating point comparisons
- **[data]**: Supported cryptos, fiats, operations, trading pairs, CSV field mappings, and datetime parsing formats
- **[logging]**: Log level and format configuration

**IMPORTANT**: The position accounting method (`filo` vs `fifo`) in `config.toml` fundamentally changes how capital gains are calculated. FILO (First-In-Last-Out) is the default.

## Core Architecture

### Main Components

- **main.py**: Entry point that processes CSV files, creates transactions, and generates annual statements
- **config_loader.py**: Loads and manages configuration from config.toml (Python 3.11+ uses native tomllib, older versions use toml package)
- **shared_def.py**: Imports configuration and exposes it as module constants (CRYPTOS, FIATS, etc.)
- **transaction.py**: Handles parsing and validation of individual trading transactions from CSV rows with configurable datetime parsing
- **annual_statement.py**: Manages financial year tax calculations, portfolio tracking, and gain/loss reporting
- **portfolio.py**: Implements FILO/FIFO position tracking and capital gains/loss calculations
- **position.py**: Represents individual crypto positions with cost basis tracking
- **gain_loss.py**: Calculates capital gains/losses for tax reporting
- **logger.py**: Simple logging configuration

### Data Flow

1. Configuration is loaded from `config.toml` via `config_loader.py`
2. CSV files are parsed using field mappings from the loaded configuration
3. Each valid row creates a `Transaction` object with datetime parsing and validation
4. Transactions are sorted chronologically if `sort_by_datetime_asc` is true
5. Transactions are grouped by financial year into `AnnualStatement` objects
6. Each statement maintains a `Portfolio` that tracks crypto positions using FILO or FIFO accounting
7. Capital gains/losses are calculated when crypto is sold and positions are matched
8. Detailed CSV records are printed to stdout for each gain/loss event
9. Annual tax reports are generated showing gains, losses, and portfolio balances

### Key Design Decisions

- **Configurable accounting**: Supports both FILO (Last-In-First-Out) and FIFO (First-In-First-Out) accounting for crypto position matching via config.toml
- **Australian tax compliance**: Fiscal year runs July-June; discountable gains (held >12 months) get 50% CGT discount
- **Precision handling**: Uses configurable `precision_threshold` (default: 0.00000001) for floating point comparisons to avoid rounding errors
- **Fee handling**: Crypto fees paid trigger disposal events with incidental loss calculations; fiat fees are treated as incidental losses
- **Non-buy/sell operations**: Deposit, withdrawal, and loss operations are processed differently - fees in crypto trigger tax events
- **Chronological processing**: Transactions must be processed in datetime order to maintain accurate position tracking
- **Portfolio persistence**: Each financial year carries forward portfolio and losses from the previous year

### Transaction Processing Logic

**Buy/Sell transactions** (portfolio.py:20-125):
- Creates new positions when buying crypto
- Matches and disposes positions when selling crypto (FILO/FIFO based on config)
- Calculates gains/losses by comparing disposal proceeds vs cost base
- Handles fees paid in crypto as separate disposal events
- Handles fees paid in fiat as incidental losses

**Non-buy/sell transactions** (portfolio.py:127-188):
- Withdrawal, deposit, and loss operations
- Fees paid in crypto trigger disposal events
- Cost base of disposed crypto fee is treated as incidental loss

**Loss disposals** (portfolio.py:190-212):
- Used for explicit loss recording (e.g., lost wallet, theft)
- Disposes positions at zero value, crystallizing losses

## CSV Format Requirements

The application expects CSV files with specific columns. Column names are mapped via `[data.fields]` in config.toml:

- **Datetime**: When the trade happened (required) - supports multiple formats via config
- **Operation**: 'Buy', 'Sell', 'Deposit', 'Withdrawal', or 'Loss' (required for processing)
- **Pair**: Trading pair (e.g., btcusd, btcaud, ethusd) - must exist in `[data.pair_split_map]`
- **Crypto amounts**: BTC, LTC, NMC, ETH, BCH columns (optional, depending on transaction)
- **Fiat amounts**: USD, AUD columns (optional, depending on transaction)
- **Fee columns**: Fee(BTC), Fee(LTC), Fee(NMC), Fee(ETH), Fee(BCH), Fee(USD), Fee(AUD)
- **Exchange rates**: BTCUSD, BTCAUD, LTCUSD, LTCBTC, NMCUSD, ETHUSD, ETHBTC, BCHUSD, AUDUSD
- **Optional**: Type, Exchange, Comments

See README.md for complete CSV format specification and example.csv for a working example.

## Supported Assets

Currently configured to support:
- **Cryptocurrencies**: BTC, ETH, LTC, NMC, BCH
- **Fiat currencies**: USD, AUD
- **Trading pairs**: btcusd, btcaud, ltcusd, nmcusd, xethxxbt, xethzusd, ethusd, xltczusd, xxbtzusd, xltcxxbt, bchusd

To add support for new assets, update `config.toml` and ensure proper field mappings.

## Limitations

- No automated exchange log parsing (manual CSV transformation required)
- Limited to assets defined in config.toml
- Specific trading pairs only (see config.toml [data.pair_split_map] for full list)
- Designed specifically for Australian tax calculations (July-June fiscal year)
- No test suite currently exists
- No database persistence - all processing is in-memory from CSV files
