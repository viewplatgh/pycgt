import sys
import pprint
import csv
import copy
from datetime import datetime
from transaction import Transaction
from annual_statement import AnnualStatement

fields = {
    'Type': '_type',
    'Exchange': 'exchange',
    'Datetime': 'datetime',
    'Operation': 'operation',
    'Pair': 'pair',
    'BTC': 'btc',
    'LTC': 'ltc',
    'NMC': 'nmc',
    'ETH': 'eth',
    'USD': 'usd',
    'AUD': 'aud',
    'Fee(BTC)': 'fee_btc',
    'Fee(USD)': 'fee_usd',
    'Fee(AUD)': 'fee_aud',
    'BTCAUD': 'btcaud',
    'BTCUSD': 'btcusd',
    'LTCUSD': 'ltcusd',
    'LTCBTC': 'ltcbtc',
    'NMCUSD': 'nmcusd',
    'ETHUSD': 'ethusd',
    'ETHBTC': 'ethbtc',
    'AUDUSD': 'audusd',
    'Comments': 'comments'
}

pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)

statements = []
print('{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}'.format(
    'gain_or_loss', 'aud', 'discountable', 'buy_transaction.aud',
    'buy_transaction.volume', 'buy_transaction.datetime',
    'buy_transaction.operation', 'buy_transaction.pair', 'buy_transaction.usd',
    'position.asset', 'position.aud', 'position.initial_volume',
    'position.price', 'position.volume', 'matched', 'sell_transaction.aud',
    'sell_transaction.volume', 'sell_transaction.datetime',
    'sell_transaction.operation', 'sell_transaction.pair',
    'sell_transaction.usd'))
for item in sys.argv[1:]:
  with open(item, 'r') as csvfile:
    csvcontent = csv.reader(csvfile, delimiter=',', quotechar='"')
    parsed_combined_trans = []
    attrs = None
    for index, row in enumerate(csvcontent):
      if index == 0:
        attrs = list(map(lambda x: '' if x not in fields else fields[x], row))
      else:
        values = list(map(lambda x: x.strip(), row))
        operidx = next(i for i, v in enumerate(attrs) if v == 'operation')
        current_trans = None
        if str(values[operidx]).lower() in [
            'buy', 'sell', 'deposit', 'withdrawal', 'loss'
        ]:
          try:
            current_trans = Transaction.createFrom(attrs=attrs, values=values)
          except BaseException as exp:
            pp.pprint(exp)
            continue
          parsed_combined_trans.append(current_trans)
        else:
          continue
    for tran in parsed_combined_trans:
      if tran.fiscal_year > 1900:
        statement = next(
            (item for item in statements if item[0] == tran.fiscal_year), None)
        if statement:
          statement[1].process_transaction(tran)
        else:
          previous_statement = statements[-1][1] if len(statements) else None
          previous_portfolio = copy.deepcopy(
              previous_statement.portfolio) if previous_statement else None
          if previous_statement:
            previous_statement.create_fee_loss()
          statement = AnnualStatement(
              fiscal_year=tran.fiscal_year,
              portfolio=previous_portfolio,
              losses=previous_statement.carried_losses
              if previous_statement else None)
          statement.process_transaction(tran)
          statements.append((tran.fiscal_year, statement))
      else:
        previous_statement = statements[-1][1] if len(statements) else None
        if previous_statement:
          previous_statement.process_transaction(tran)
        else:
          raise Exception('Not knowing which year is the transaction')

for item in statements:
  item[1].report()
