import sys
import pprint
import csv
import copy
from transaction import Transaction
from annual_statement import AnnualStatement
from shared_def import OPERATIONS, FIELDS

from logger import logger


pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)

statements = []
statements_dict = {}
print('{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}'.format(
    'gain_or_loss', 'datetime', 'aud', 'discountable', 'description', 'buy_transaction.aud',
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
    parsed_trans = []
    attrs = None
    for index, row in enumerate(csvcontent):
      if index == 0:
        # parse header
        attrs = list(map(lambda x: '' if x not in FIELDS else FIELDS[x], row))
      else:
        values = list(map(lambda x: x.strip(), row))
        operidx = next(i for i, v in enumerate(attrs) if v == 'operation')
        current_trans = None
        if str(values[operidx]).lower() in OPERATIONS:
          try:
            current_trans = Transaction.createFrom(attrs=attrs, values=values)
          except BaseException as exp:
            logger.error(pp.pformat(exp))
            raise
          parsed_trans.append(current_trans)
        else:
          continue
    for tran in parsed_trans:
      statement = statements_dict.get(tran.financial_year)
      if statement:
        statement.process_transaction(tran)
      else:
        # new financial year, create new statement
        previous_statement = statements[-1][1] if len(statements) else None
        previous_portfolio = copy.deepcopy(
            previous_statement.portfolio) if previous_statement else None
        statement = AnnualStatement(
            financial_year=tran.financial_year,
            portfolio=previous_portfolio,
            losses=previous_statement.carried_losses
            if previous_statement else None)
        statement.process_transaction(tran)
        statements.append((tran.financial_year, statement))
        statements_dict[tran.financial_year] = statement

for item in statements:
  item[1].report()
