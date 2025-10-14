import re
import pprint
import copy
from datetime import datetime
from dateutil import parser
from shared_def import (
    FY_START_MONTH, FIATS, CRYPTOS, PAIR_SPLIT_MAP,
    LOCALE_FIAT, PARSE_DATETIME_FORMATS, FIELDS
)
from logger import logger

pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)

no_parser = lambda x: x


def float_parser(x):
  """ float parser """
  if not x:
    return float(0)
  try:
    result = float(x)
    return result
  except BaseException as _:
    matched = re.match(r"[-+]?\d*\.*\d+", x)
    if matched:
      return float(matched.group())
    raise


def datetime_parser(x):
  """ datetime parser """
  if not x:
    return None

  for fmt in PARSE_DATETIME_FORMATS:
    try:
      result = datetime.strptime(x, fmt)
      return result
    except BaseException as _:
      continue

  try:
    result = parser.parse(x)
    return result
  except BaseException as _:
    logger.error(f"Failed to parse datetime '{x}'")
    raise


# [data.fields] configured fields parsers
PARSER_MAP = {
    '_type': no_parser,
    'exchange': no_parser,
    'datetime': datetime_parser,
    'operation': lambda x: str(x).lower(),
    'pair': lambda x: str(x).lower(),
    'comments': no_parser,
}

def _add_crypto_fiat_parsers():
  """
  Add float_parser for all crypto/fiat fields from FIELDS.
  Any field not already in PARSER_MAP is assumed to be a numeric field.
  """
  for field_value in FIELDS.values():
    if field_value not in PARSER_MAP:
      PARSER_MAP[field_value] = float_parser

_add_crypto_fiat_parsers()


class Transaction(dict):
  def __init__(self):
    super(Transaction, self).__init__()
    for key, value in PARSER_MAP.items():
      self[key] = value('')
    self['volume'] = None

  @classmethod
  def createFrom(cls, attrs, values):
    """ create """
    trans = Transaction()
    zipped = zip(attrs, values)
    for item in zipped:
      if item[0] in PARSER_MAP:
        trans[item[0]] = PARSER_MAP[item[0]](item[1])

    if trans.datetime is None:
      raise Exception('Missing datetime in transaction: {}'.format(pp.pformat(trans)))
    return trans

  def __getattr__(self, name):
    """
    Dynamically provide property access to all fields.
    """
    if name in FIELDS.values() or name == 'volume':
      return self[name]
    
    raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

  def __setattr__(self, name, value):
    """
    Dynamically provide property setters for all fields.
    """
    if name in FIELDS.values() or name == 'volume':
      self[name] = value
    else:
      super().__setattr__(name, value)

  @property
  def fiat(self):
    """Returns the fiat amount based on LOCALE_FIAT configuration"""
    return self[LOCALE_FIAT.lower()]

  @fiat.setter
  def fiat(self, value):
    self[LOCALE_FIAT.lower()] = value

  @property
  def left2right(self):
    """ return a tuple which indicates the transaction is from which(left) to which(right) """
    if self.pair and not self.pair in PAIR_SPLIT_MAP:
      raise Exception('Unexpected pair: {}'.format(self.pair))
    if not self.operation in ['buy', 'sell']:
      return ('', '')

    splitted = tuple(PAIR_SPLIT_MAP[self.pair]) if self.pair else ('', '')
    return (splitted[1], splitted[0]) if self.operation == 'buy' else splitted

  @property
  def financial_year(self):
    if self.datetime.month < FY_START_MONTH:
      return self.datetime.year
    else:
      return self.datetime.year + 1

  BRIEF_KEYS = ['datetime', 'operation', 'pair', LOCALE_FIAT.lower(), 'usd', 'volume']

  @property
  def brief(self):
    """ return a dict which contains brief information of this transaction """
    brief_keys = Transaction.BRIEF_KEYS[:-1] # exclude volume
    result = dict(**{my_key: self[my_key] for my_key in brief_keys})
    if self.volume is not None:
      result.update(volume=self.volume)
    else:
      volume_key = None
      left2right = self.left2right
      if self.operation == 'buy':
        volume_key = left2right[1]
      elif self.operation == 'sell':
        volume_key = left2right[0]
      else:
        for item in CRYPTOS:
          if self[item] > 0:
            volume_key = item
            break
        if volume_key is None:
          for item in FIATS:
            if self[item] > 0:
              volume_key = item
              break
      if volume_key:
        result.update(volume=self[volume_key])
      else:
        logger.warning('Cannot find volume for transaction: {}'.format(pp.pformat(self)))
        result.update(volume='N/A')
    return result

  @staticmethod
  def create_na_brief():
    return dict(
        **{
            my_key: 'N/A'
            for my_key in
            Transaction.BRIEF_KEYS
        })

  @staticmethod
  def mock_sell_transaction(tran):
    """ create mock sell transaction from a non buy/sell transaction crypto fee """
    if tran.operation in ['buy', 'sell']:
      raise Exception('Cannot mock sell transaction from buy/sell transaction')
    mocked = copy.deepcopy(tran)
    mocked.operation = 'sell'
    fee_crypto = None
    for crypto in CRYPTOS:
      crypto_fee_field = 'fee_{}'.format(crypto)
      if crypto_fee_field in tran:
        volume = tran[crypto_fee_field]
        if volume > 0:
          fee_crypto = crypto
          mocked[fee_crypto] = tran[crypto_fee_field]
          mocked.volume = tran[crypto_fee_field]
          mocked[crypto_fee_field] = 0
          break
    if not fee_crypto:
      raise Exception('Cannot find crypto fee in transaction')
    mocked.pair = '{}{}'.format(fee_crypto, LOCALE_FIAT).lower()
    fiat_fee_field = 'fee_{}'.format(LOCALE_FIAT.lower())
    mocked[LOCALE_FIAT.lower()] = tran[fiat_fee_field] if fiat_fee_field in tran else 0
    mocked[fiat_fee_field]
    return mocked
