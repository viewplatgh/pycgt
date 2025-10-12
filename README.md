# pycgt

A capital gain tax calculator for crypto traders or investors with configurable locale support. While originally designed for Australian tax returns, it supports any fiat currency through configuration.

## Features

- **Locale-aware calculations**: Configure your local fiat currency (AUD, USD, etc.) for cost basis and reporting
- **Flexible accounting**: Supports both FILO (Last-In-First-Out) and FIFO (First-In-First-Out) position matching
- **Exchange log transformation**: Built-in transformer for Bitstamp exports, extensible for other exchanges
- **Comprehensive fee handling**: Crypto fees trigger disposal events; fiat fees treated as incidental losses
- **Australian tax compliance**: CGT discount for assets held >12 months, configurable fiscal year

## Known Limitations

- Exchange transformer support is limited (currently only Bitstamp; manual transformation required for other exchanges)
- No automated market data fetching for missing exchange rates
- Limited to assets defined in config.toml:
  - **Supported cryptos**: BTC, ETH, LTC, NMC, BCH, LINK
  - **Supported fiats**: USD, AUD
  - **Supported pairs**: btcusd, btcaud, ltcusd, ltcbtc, nmcusd, ethusd, ethbtc, bchusd, linkusd, linkaud, audusd, and Kraken-style pairs (xethxxbt, xethzusd, etc.)

## Configuration

All settings are in `config.toml`:

```toml
[locale]
fiat = "aud"           # Local fiat currency (aud, usd, etc.)
fy_start_month = 7     # Fiscal year start month (7 = July for Australian tax)

[options]
position_accounting = "filo"     # "filo" or "fifo"
sort_by_datetime_asc = true
precision_threshold = 0.00000001

[data]
cryptos = ["btc", "ltc", "nmc", "eth", "bch", "link"]
fiats = ["usd", "aud"]
operations = ["buy", "sell", "deposit", "withdrawal", "loss"]
# ... see config.toml for full configuration
```

**Important**: The `locale.fiat` setting determines which currency is used for all cost basis calculations and tax reporting.

## Trading Logs pycgt Can Process

pycgt expects CSV files with specific columns. Column names are configurable via `[data.fields]` in config.toml:

**Required columns:**
- **Datetime**: When the trade happened (multiple formats supported)
- **Operation**: 'Buy', 'Sell', 'Deposit', 'Withdrawal', or 'Loss'

**Optional columns:**
- **Type**: Transaction type description
- **Exchange**: The exchange where the trade was made
- **Pair**: Trading pair (e.g., btcusd, btcaud, ethusd)
- **Crypto amounts**: BTC, LTC, NMC, ETH, BCH, LINK
- **Fiat amounts**: USD, AUD
- **Fee columns**: Fee(BTC), Fee(LTC), Fee(NMC), Fee(ETH), Fee(BCH), Fee(LINK), Fee(USD), Fee(AUD)
- **Exchange rates**: BTCUSD, BTCAUD, LTCUSD, LTCBTC, NMCUSD, ETHUSD, ETHBTC, BCHUSD, LINKUSD, LINKAUD, AUDUSD
- **Comments**: Any notes about the transaction

CSV example (see example.csv):

```csv
Type,Exchange,Datetime,Operation,Pair,BTC,LTC,NMC,ETH,BCH,LINK,USD,AUD,Fee(BTC),Fee(LTC),Fee(NMC),Fee(ETH),Fee(BCH),Fee(LINK),Fee(USD),Fee(AUD),BTCAUD,BTCUSD,LTCUSD,LTCBTC,NMCUSD,ETHUSD,ETHBTC,BCHUSD,LINKUSD,LINKAUD,AUDUSD,Comments
Market,Coinbase,"2024-03-14T09:11:00.711Z",Buy,BTCAUD,1,,,,,,,,108524.67,,,,,,,108.52467,108633.19467,,,,,,,,,,,
Market,Coinbase,"2025-06-30T13:40:11.735Z",Sell,BTCAUD,0.998,,,,,,,162387.8306,,,,,,,,162.87646,162713.15,,,,,,,,,,,,
```

## How to Run

Python 3 is required. Using virtualenv is recommended.

### 1. Prepare Python Environment

```sh
python3 -m venv .virtualenv       # Create virtualenv
source .virtualenv/bin/activate   # Activate virtualenv
pip install --upgrade pip         # Upgrade pip
pip install -r requirements.txt   # Install dependencies
```

### 2. Generate CGT Reports (Default Mode)

Process pycgt-formatted CSV files:

```sh
python main.py [csv_files...]
```

Example:

```sh
python main.py example.csv
python main.py file1.csv file2.csv  # Multiple files supported
```

### 3. Transform Exchange Logs (Transform Mode)

Convert exchange exports to pycgt format:

```sh
python main.py -t -x EXCHANGE [-o OUTPUT] INPUT_FILES...
```

Example:

```sh
# Transform Bitstamp export
python main.py -t -x bitstamp Bitstamp-Export.csv

# Custom output filename
python main.py -t -x bitstamp -o converted.csv Bitstamp-Export.csv
```

Supported exchanges: `bitstamp`

## Example Output

When processing example.csv with `fiat = "aud"` in config.toml:

```log
gain_or_loss,datetime,aud,discountable,description,buy_transaction.aud,buy_transaction.volume,...
loss,2024-09-07 09:11:00.711000+00:00,-27.46,N/A,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,...
gain,2025-03-15 09:11:00.711000+00:00,24.65,Yes,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,...
gain,2025-06-30 13:40:11.735000+00:00,54080.54,Yes,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,...
========================================================
Tax return report for year: 2024
Gross gains of the year: $0.00 AUD
Taxable gains of the year: $0.00 AUD
Net gains of the year:  $0.00 AUD
Portfolio of the year:
  btc: 1.0
  ltc: 0
  nmc: 0
  eth: 0
  bch: 0
  link: 0
========================================================

========================================================
Tax return report for year: 2025
Gross gains of the year: $54159.43 AUD
Discountable gains of the year: $54159.43 AUD
Taxable gains of the year: $27079.72 AUD
Net gains of the year:  $26753.82 AUD
Portfolio of the year:
  btc: 8.67e-19
  ltc: 0
  ...
========================================================
```

**Note**: The currency label (AUD) in the output adapts based on the `locale.fiat` setting in config.toml. If you set `fiat = "usd"`, all outputs will show USD instead.

## Extending pycgt

### Adding New Cryptocurrencies

To add support for a new cryptocurrency:

1. Update `config.toml`:
   ```toml
   [data]
   cryptos = ["btc", "ltc", "nmc", "eth", "bch", "link", "your_coin"]
   ```

2. Add field mappings:
   ```toml
   [data.fields]
   "YOUR_COIN" = "your_coin"
   "Fee(YOUR_COIN)" = "fee_your_coin"
   ```

3. Add trading pairs:
   ```toml
   [data.pair_split_map]
   your_coinusd = ["your_coin", "usd"]
   your_coinaud = ["your_coin", "aud"]
   ```

### Adding Exchange Transformers

To add support for a new exchange:

1. Create `transformer/your_exchange_transformer.py` inheriting from `BaseTransformer`
2. Implement the `transform()` method to convert the exchange's CSV format
3. Register it in `transformer/__init__.py`:
   ```python
   elif exchange_type == 'your_exchange':
       return YourExchangeTransformer(input_files, output_file)
   ```

See `transformer/bitstamp_transformer.py` for reference implementation.

## License

Distributed under the GNU General Public License v3.0. See LICENSE for more information.

## Contact

Rob Lao - viewpl(at)gmail(dot)com
