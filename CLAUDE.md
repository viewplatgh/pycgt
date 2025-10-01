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

## Core Architecture

### Main Components

- **main.py**: Entry point that processes CSV files, creates transactions, and generates annual statements
- **transaction.py**: Handles parsing and validation of individual trading transactions from CSV rows
- **annual_statement.py**: Manages financial year tax calculations, portfolio tracking, and gain/loss reporting
- **portfolio.py**: Implements FILO (First-In-Last-Out) position tracking and capital gains/loss calculations
- **position.py**: Represents individual crypto positions with cost basis tracking
- **gain_loss.py**: Calculates capital gains/losses for tax reporting
- **shared_def.py**: Defines supported cryptocurrencies, operations, and CSV field mappings

### Data Flow

1. CSV files are parsed using field mappings from `shared_def.py`
2. Each valid row creates a `Transaction` object with datetime parsing and validation
3. Transactions are grouped by financial year into `AnnualStatement` objects
4. Each statement maintains a `Portfolio` that tracks crypto positions using FILO accounting
5. Capital gains/losses are calculated when crypto is sold and positions are matched
6. Annual tax reports are generated showing gains, losses, and portfolio balances

### Key Design Decisions

- Uses FILO (Last-In-First-Out) accounting for crypto position matching
- Fiscal year runs July-June for Australian tax compliance
- Supports limited currency pairs and exchange rates
- Processes transactions chronologically to maintain accurate position tracking

## CSV Format Requirements

The application expects CSV files with specific columns including:

- Datetime, Operation (Buy/Sell), Pair (trading pair)
- Crypto amounts: BTC, LTC, NMC, ETH
- Fiat amounts: USD, AUD
- Fee amounts for each currency
- Exchange rates: BTCUSD, LTCUSD, etc.

See README.md for complete CSV format specification and example.

## Limitations

- No automated exchange log parsing (manual CSV transformation required)
- Limited to 4 cryptocurrencies: BTC, ETH, LTC, NMC
- Limited to 2 fiat currencies: USD, AUD
- Specific trading pairs only (see shared_def.py for full list)
- Designed specifically for Australian tax calculations
