# pycgt

A capital gain tax calculator for crypto traders or investors. This is just a toy script, not a mature product. Please notice following known limits of it:

- cannot process raw logs from any exchanges, you need to transform your trading logs into pycgt's format before using it
- limited currency types
  - supported cryptos: BTC, ETH, LTC, NMC
  - supported fiats: USD, AUD
- limited trading pairs
  - supported pairs: btcusd, btcaud, ltcusd, nmcusd, xethxxbt, xethzusd, ethusd, xltczusd, xxbtzusd, xltcxxbt
- designed for Australian tax return, e.g. assuming financial year end between June and July

## trading logs pycgt can process

A csv file with following column:

- Type
  - optional, transaction type
- Exchange
  - optional, the exchange where the trade was made
- Datetime
  - important, when the trade happened
- Operation
  - important, either 'Buy' or 'Sell' if it's a trading transaction
- Pair
  - important, one of "btcusd, btcaud, ltcusd, nmcusd, xethxxbt, xethzusd, ethusd, xltczusd, xxbtzusd, xltcxxbt"
- BTC
  - optional, the BTC amount issued with the trade
- LTC
  - optional, the LTC amount issued with the trade
- NMC
  - optional, the NMC amount issued with the trade
- USD
  - the USD amount issued with the trade
- AUD
  - the AUD amount issued with the trade
- Fee(BTC)
  - optional, fees paid in BTC
- Fee(LTC)
  - optional, fees paid in LTC
- Fee(NMC)
  - optional, fees paid in NMC
- Fee(USD)
  - optional, fees paid in USD
- Fee(AUD)
  - optional, fees paid in USD
- BTCAUD
  - optional, BTCAUD exchange rate at "Datetime"
- BTCUSD
  - optional, BTCUSD exchange rate at "Datetime"
- LTCUSD
  - optional, LTCUSD exchange rate at "Datetime"
- NMCUSD
  - optional, NMCUSD exchange rate at "Datetime"
- AUDUSD
  - optional, AUDUSD exchange rate at "Datetime"
- Comments
  - optional, just any comments

A csv example (see example.csv):

```csv
Type,Exchange,Datetime,Operation,Pair,BTC,LTC,USD,AUD,Fee(BTC),Fee(LTC),Fee(USD),Fee(AUD),BTCUSD,LTCUSD,LTCBTC,AUDUSD,Comments
Market,Coinbase,"2015-12-12T09:11:00.711Z",Buy,BTCUSD,1,,,420,525,,,1.61,1.99,420,,,0.8,
Market,Coinbase,"2017-07-07T13:40:11.735Z",Sell,BTCUSD,1,,,1838.53,2298.1625,,,4.71,6.05,1838.53,,,0.8,
```

## How to run it

python3 is required, using virtualenv is recommended

### 1. Prepare python environment

```sh
python3.x -m venv .virtualenv       # install virtualenv
source .virtualenv/bin/activate     # activate virtualenv
pip install --upgrade pip           # upgrade pip
pip install -r requirements.txt     # install required packages
```

### 2. Run command to generate tax return statements and reports

```sh
python main.py [csv files] # multiple csv files are supported, use space to seperate them
```

Example:

```sh
python main.py example.csv
```

if everything is ok, the output would be:

```log
gain_or_loss,datetime,aud,discountable,description,buy_transaction.aud,buy_transaction.volume,buy_transaction.datetime,buy_transaction.operation,buy_transaction.pair,buy_transaction.usd,position.asset,position.aud,position.initial_volume,position.price,position.volume,matched,sell_transaction.aud,sell_transaction.volume,sell_transaction.datetime,sell_transaction.operation,sell_transaction.pair,sell_transaction.usd
loss,2024-09-07 09:11:00.711000+00:00,-27.46421467,N/A,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,buy,btcaud,0.0,btc,108633.19467,1.0,108633.19467,1.0,0.001,0.0,0.999,2024-09-07 09:11:00.711000+00:00,sell,btcaud,0.0
loss,2024-09-07 09:11:00.711000+00:00,-108.63319467,N/A,Incidental loss because of fee paid in crypto,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,0,0.0,0.001,2024-09-07 09:11:00.711000+00:00,withdrawal,,0.0
gain,2025-03-15 09:11:00.711000+00:00,24.652365330000002,Yes,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,buy,btcaud,0.0,btc,108633.19467,1.0,108633.19467,0.999,0.001,0.0,0.998,2025-03-15 09:11:00.711000+00:00,sell,btcaud,0.0
loss,2025-03-15 09:11:00.711000+00:00,-108.63319467,N/A,Incidental loss because of fee paid in crypto,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,0,0.0,0.001,2025-03-15 09:11:00.711000+00:00,withdrawal,,0.0
gain,2025-06-30 13:40:11.735000+00:00,54080.53551400998,Yes,,108524.67,1.0,2024-03-14 09:11:00.711000+00:00,buy,btcaud,0.0,btc,108633.19467,1.0,108633.19467,0.998,0.997,162387.8306,0.997,2025-06-30 13:40:11.735000+00:00,sell,btcaud,0.0
loss,2025-06-30 13:40:11.735000+00:00,-162.87646,N/A,Incidental loss because of fee paid in fiat,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,N/A,0,162387.8306,0.997,2025-06-30 13:40:11.735000+00:00,sell,btcaud,0.0
========================================================
Tax return report for year: 2024
Gross gains of the year: $0.00 AUD
Discountable gains of the year: $0.00 AUD
Non-discountable gains of the year: $0.00 AUD
Taxable gains of the year: $0.00 AUD
Losses carried from previous year: - $0.00 AUD
Losses of this year only: - $0.00 AUD
Total losses at the end of the year: - $0.00 AUD
Net gains of the year:  $0.00 AUD
Portfolio of the year:
  btc: 1.0
  ltc: 0
  nmc: 0
  eth: 0
========================================================

========================================================
Tax return report for year: 2025
Gross gains of the year: $54105.19 AUD
Discountable gains of the year: $54105.19 AUD
Non-discountable gains of the year: $0.00 AUD
Taxable gains of the year: $27052.59 AUD
Losses carried from previous year: - $0.00 AUD
Losses of this year only: - $407.61 AUD
Total losses at the end of the year: - $407.61 AUD
Net gains of the year:  $26644.99 AUD
Portfolio of the year:
  btc: 0.0010000000000000009
  ltc: 0
  nmc: 0
  eth: 0
========================================================
```

## License

Distributed under the GNU General Public License v3.0. See LICENSE for more information.

## Contact

Rob Lao - viewpl(at)gmail(dot)com
