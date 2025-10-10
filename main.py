import sys
import pprint
import csv
import copy
import argparse
from transaction import Transaction
from annual_statement import AnnualStatement
from shared_def import SORT_BY_DATETIME_ASC, OPERATIONS, FIELDS

from logger import logger


pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)


def process_cgt_report(csv_files):
  """Process CSV files and generate CGT reports"""
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

  parsed_trans = []
  for item in csv_files:
    with open(item, 'r') as csvfile:
      csvcontent = csv.reader(csvfile, delimiter=',', quotechar='"')
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

  if SORT_BY_DATETIME_ASC:
    parsed_trans.sort(key=lambda x: x.datetime)
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


def transform_logs(csv_files, exchange_type, output_file):
  """Transform exchange logs to pycgt format"""
  from transformer import get_transformer

  logger.info(f"Transforming {len(csv_files)} file(s) from {exchange_type} format to pycgt format")
  logger.info(f"Output will be written to: {output_file}")

  try:
    transformer = get_transformer(exchange_type, csv_files, output_file)
    transformer.transform()
    logger.info("Transformation completed successfully")
  except ValueError as e:
    logger.error(str(e))
    sys.exit(1)
  except Exception as e:
    logger.error(f"Transformation failed: {e}")
    raise


def main():
  """Main entry point with argument parsing"""
  parser = argparse.ArgumentParser(
      description='pycgt - Capital Gains Tax calculator for crypto investors/traders',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
Examples:
  # Generate CGT report from pycgt-formatted CSV files:
  python main.py file1.csv file2.csv

  # Transform exchange logs to pycgt format:
  python main.py -t -x bitstamp -o output.csv input.csv
      """)

  parser.add_argument('files', nargs='+', metavar='FILE',
                      help='CSV file(s) to process')
  parser.add_argument('-t', '--transform', action='store_true',
                      help='Transform exchange logs to pycgt format')
  parser.add_argument('-x', '--exchange', type=str, metavar='EXCHANGE',
                      help='Exchange type (e.g., bitstamp) - required with -t')
  parser.add_argument('-o', '--output', type=str, metavar='OUTPUT',
                      help='Output filename for transformed CSV - required with -t')

  args = parser.parse_args()

  # Validate transform mode arguments
  if args.transform:
    if not args.exchange:
      parser.error('-t/--transform requires -x/--exchange to be specified')
    if not args.output:
      parser.error('-t/--transform requires -o/--output to be specified')
    transform_logs(args.files, args.exchange, args.output)
  else:
    # Default mode: CGT report generation
    if args.exchange or args.output:
      parser.error('-x/--exchange and -o/--output can only be used with -t/--transform')
    process_cgt_report(args.files)


if __name__ == '__main__':
  main()
