# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pycgt is a capital gain tax calculator for crypto traders/investors with configurable locale support. While originally designed for Australian tax returns, it supports any fiat currency through configuration. It processes CSV files containing trading transaction logs and generates annual tax statements with capital gains/losses calculations.

## Environment Setup

```bash
python3 -m venv .virtualenv
source .virtualenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Application

- Remember to activate the virtual environment before running python main.py to test, i.e. source .virtualenv/bin/activate && python main.py ...

### CGT Report Mode (Default)

Process pycgt-formatted CSV files and generate capital gains tax reports:

```bash
python main.py [csv_files...]
```

Example:

```bash
python main.py example.csv
python main.py one-example.csv two-example.csv
```

The application outputs CSV-formatted gain/loss records to stdout, followed by annual tax summaries. You can redirect output to a file if needed:

```bash
python main.py example.csv > results.csv
```

### Transform Mode

Transform exchange-exported logs into pycgt format:

```bash
python main.py -t -x EXCHANGE [-o OUTPUT] INPUT_FILES...
```

Example:

```bash
# Transform Bitstamp export to pycgt format
python main.py -t -x bitstamp Bitstamp-Export.csv

# Specify custom output filename
python main.py -t -x bitstamp -o converted.csv Bitstamp-Export.csv
```

**Supported Exchanges:**

- `bitstamp` - Bitstamp transaction export format
- `independentreserve` - Independent Reserve transaction export format
- `nexo` - Nexo transaction export format

If `-o` is not specified, output filename is auto-generated as `[input-basename]-transformed-[random].csv`.

## Configuration

All settings are centralized in `config.toml`:

- **[locale]**:
  - `fiat`: Local fiat currency (default: "aud") - determines which currency is used for cost basis and reporting
  - `fy_start_month`: Fiscal year start month (default: 7 for July, used in Australian tax)
- **[options]**:
  - `position_accounting`: Method for matching positions - "filo" (Last-In-First-Out) or "fifo" (First-In-First-Out)
  - `sort_by_datetime_asc`: Sort transactions chronologically (default: true)
  - `precision_threshold`: Floating point comparison threshold (default: 0.00000001)
- **[data]**:
  - `cryptos`: List of supported cryptocurrencies
  - `fiats`: List of supported fiat currencies
  - `operations`: Supported transaction types (buy, sell, deposit, withdrawal, gain, loss)
  - `parse_datetime_formats`: Custom datetime formats to try before falling back to dateutil parser
  - `[data.fields]`: CSV column name mappings
  - `[data.pair_split_map]`: Trading pair definitions (e.g., btcusd = ["btc", "usd"])
- **[logging]**: Log level and format configuration

**IMPORTANT**:

- The `locale.fiat` setting determines which currency is used throughout the application for cost basis calculation and tax reporting. All output will be in this currency.
- The position accounting method (`filo` vs `fifo`) fundamentally changes how capital gains are calculated. FILO (Last-In-First-Out) is the default.

## Core Architecture

### Main Components

**Core Processing:**

- **main.py**: Entry point with argument parsing, supports both CGT report generation and exchange log transformation
- **config_loader.py**: Loads and manages configuration from config.toml (Python 3.11+ uses native tomllib, older versions use toml package)
- **shared_def.py**: Imports configuration and exposes it as module constants (CRYPTOS, FIATS, LOCALE_FIAT, etc.)
- **transaction.py**: Handles parsing and validation of individual trading transactions from CSV rows with configurable datetime parsing
- **annual_statement.py**: Manages financial year tax calculations, portfolio tracking, and gain/loss reporting
- **portfolio.py**: Implements FILO/FIFO position tracking and capital gains/loss calculations
- **position.py**: Represents individual crypto positions with cost basis tracking in locale fiat
- **gain_loss.py**: Calculates capital gains/losses for tax reporting in locale fiat
- **logger.py**: Simple logging configuration
- **utils.py**: Utility functions (e.g., auto-generating output filenames)

**Transformer Module:**

- **transformer/base_transformer.py**: Abstract base class for exchange log transformers
- **transformer/bitstamp_transformer.py**: Bitstamp-specific transformer implementation
- **transformer/independent_reserve_transformer**: IndependentReserve-specific transformer implementation
- **transformer/nexo_transformer**: Nexo-specific transformer implementation
- **transformer/**init**.py**: Exports `get_transformer()` factory function

### Data Flow

1. Configuration is loaded from `config.toml` via `config_loader.py`
2. CSV files are parsed using field mappings from the loaded configuration
3. Each valid row creates a `Transaction` object with datetime parsing and validation
4. Transactions are sorted chronologically if `sort_by_datetime_asc` is true
5. Transactions are grouped by financial year into `AnnualStatement` objects
6. Each statement maintains a `Portfolio` that tracks crypto positions using FILO or FIFO accounting
7. Capital gains/losses are calculated when crypto is disposed and positions are matched
8. Detailed CSV records are printed to stdout for each gain/loss event
9. Annual tax reports are generated showing gains, losses, and portfolio balances

### Key Design Decisions

- **Locale fiat abstraction**: All cost basis calculations and reporting use `LOCALE_FIAT` from config - supports any fiat currency
  - Position, GainLoss, and Transaction classes use dynamic fiat property based on config
  - CSV output headers and report currency labels adapt to configured fiat
- **Configurable accounting**: Supports both FILO (Last-In-First-Out) and FIFO (First-In-First-Out) accounting for crypto position matching via config.toml
- **Tax compliance**: Fiscal year start is configurable; discountable gains (held >12 months) get 50% CGT discount (Australian rule)
- **Precision handling**: Uses configurable `precision_threshold` (default: 0.00000001) for floating point comparisons to avoid rounding errors
- **Fee handling**: Crypto fees paid trigger disposal events with incidental loss calculations; fiat fees are treated as incidental losses
- **Non-buy/sell operations**: Deposit, withdrawal, and loss operations are processed differently - fees in crypto trigger tax events
- **Chronological processing**: Transactions must be processed in datetime order to maintain accurate position tracking
- **Portfolio persistence**: Each financial year carries forward portfolio and losses from the previous year
- **Extensible transformers**: Abstract base class pattern allows easy addition of new exchange format support

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
- **Crypto amounts**: BTC, LTC, NMC, ETH, BCH, LINK columns (optional, depending on transaction)
- **Fiat amounts**: USD, AUD columns (optional, depending on transaction)
- **Fee columns**: Fee(BTC), Fee(LTC), Fee(NMC), Fee(ETH), Fee(BCH), Fee(LINK), Fee(USD), Fee(AUD)
- **Exchange rates**: BTCUSD, BTCAUD, LTCUSD, LTCBTC, NMCUSD, ETHUSD, ETHBTC, BCHUSD, AUDUSD
- **Optional**: Type, Exchange, Comments

See README.md for complete CSV format specification and example.csv for a working example.

## Supported Assets

Currently configured to support:

- **Cryptocurrencies**: BTC, ETH, LTC, NMC, BCH, LINK
- **Fiat currencies**: USD, AUD
- **Trading pairs**: btcusd, btcaud, ltcusd, ltcbtc, nmcusd, ethusd, ethbtc, bchusd, linkusd, linkaud, audusd, xethxxbt, xethzusd, xltczusd, xxbtzusd, xltcxxbt

To add support for new assets:

1. Update `[data]` section in `config.toml` (add to cryptos/fiats lists)
2. Add field mappings in `[data.fields]` (e.g., "BCH" = "bch", "Fee(BCH)" = "fee_bch")
3. Add trading pairs in `[data.pair_split_map]` (e.g., bchusd = ["bch", "usd"])
4. Note: Transaction.py PARSER_MAP auto-includes LOCALE_FIAT field, but other currencies need explicit properties

## Extending the Application

### Adding New Exchange Transformers

To add support for a new exchange:

1. Create a new transformer class in `transformer/` inheriting from `BaseTransformer`
2. Implement `transform()` method to convert exchange format to pycgt format
3. Register the transformer in `transformer/__init__.py`'s `get_transformer()` function
4. Use `CRYPTOS`, `FIATS`, and `FIELDS` from shared_def for dynamic field handling

Example structure:

```python
from transformer.base_transformer import BaseTransformer
from shared_def import CRYPTOS, FIATS, FIELDS

class MyExchangeTransformer(BaseTransformer):
    def transform(self):
        # Read exchange CSV
        # Convert to pycgt format using FIELDS.keys()
        # Write using self.write_pycgt_csv()
```

## Limitations

- Exchange transformer support is limited (currently only a few supported)
- Automated market data fetching are depending on frankfurter and bitstamp api
- Limited to assets defined in config.toml
- Specific trading pairs only (see config.toml [data.pair_split_map] for full list)
- No test suite currently exists
- No database persistence - all processing is in-memory from CSV files

## Future Enhancements

Planned improvements include:

- Add more various market data providers integration for automated exchange rate fetching
  - Add "cache", hosting a database somewhere, for forex rates data
- Abstract provider layer for pluggable market data sources (frankfurter.app, Bitstamp)
- Additional exchange transformer implementations
