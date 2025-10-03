import re
import pprint
import copy
from datetime import datetime
from dateutil import parser
from shared_def import FY_START_MONTH, CRYPTOS, PAIR_SPLIT_MAP, DEFAULT_FIAT

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
    return datetime(1899, 1, 1, 0, 0, 0)
  try:
    result = datetime.strptime(x, '%m/%d/%Y %H:%M:%S')
    return result
  except BaseException as _:
    try:
      result = datetime.strptime(x, '%b. %d, %Y, %H:%M %p')
      return result
    except BaseException as _:
      try:
        result = datetime.strptime(x, '%Y-%m-%d %H:%M:%S')
        return result
      except BaseException as _:
        try:
          result = parser.parse(x)
          return result
        except BaseException as _:
          raise


PARSER_MAP = {
    '_type': no_parser,
    'exchange': no_parser,
    'datetime': datetime_parser,
    'operation': lambda x: str(x).lower(),
    'pair': lambda x: str(x).lower(),
    'btc': float_parser,
    'ltc': float_parser,
    'nmc': float_parser,
    'eth': float_parser,
    'usd': float_parser,
    'aud': float_parser,
    'fee_btc': float_parser,
    'fee_ltc': float_parser,
    'fee_nmc': float_parser,
    'fee_eth': float_parser,
    'fee_usd': float_parser,
    'fee_aud': float_parser,
    'btcaud': float_parser,
    'btcusd': float_parser,
    'ltcusd': float_parser,
    'ltcbtc': float_parser,
    'nmcusd': float_parser,
    'ethusd': float_parser,
    'ethbtc': float_parser,
    'audusd': float_parser,
    'comments': no_parser
}



class Transaction(dict):
  def __init__(self):
    super(Transaction, self).__init__()
    for key, value in PARSER_MAP.items():
      self[key] = value('')

  @classmethod
  def createFrom(cls, attrs, values):
    """ create """
    trans = Transaction()
    zipped = zip(attrs, values)
    for item in zipped:
      if item[0] in PARSER_MAP:
        trans[item[0]] = PARSER_MAP[item[0]](item[1])
    return trans

  @property
  def _type(self):
    return self['_type']

  @_type.setter
  def _type(self, value):
    self['_type'] = value

  @property
  def exchange(self):
    return self['exchange']

  @exchange.setter
  def exchange(self, value):
    self['exchange'] = value

  @property
  def datetime(self):
    return self['datetime']

  @datetime.setter
  def datetime(self, value):
    self['datetime'] = value

  @property
  def operation(self):
    return self['operation']

  @operation.setter
  def operation(self, value):
    self['operation'] = value

  @property
  def pair(self):
    return self['pair']

  @pair.setter
  def pair(self, value):
    self['pair'] = value

  @property
  def btc(self):
    return self['btc']

  @btc.setter
  def btc(self, value):
    self['btc'] = value

  @property
  def ltc(self):
    return self['ltc']

  @ltc.setter
  def ltc(self, value):
    self['ltc'] = value

  @property
  def nmc(self):
    return self['nmc']

  @nmc.setter
  def nmc(self, value):
    self['nmc'] = value

  @property
  def eth(self):
    if 'eth' in self:
      return self['eth']
    else:
      return 0

  @eth.setter
  def eth(self, value):
    self['eth'] = value

  @property
  def usd(self):
    return self['usd']

  @usd.setter
  def usd(self, value):
    self['usd'] = value

  @property
  def aud(self):
    return self['aud']

  @aud.setter
  def aud(self, value):
    self['aud'] = value

  @property
  def fee_btc(self):
    return self['fee_btc']

  @fee_btc.setter
  def fee_btc(self, value):
    self['fee_btc'] = value

  @property
  def fee_usd(self):
    return self['fee_usd']

  @fee_usd.setter
  def fee_usd(self, value):
    self['fee_usd'] = value

  @property
  def fee_aud(self):
    return self['fee_aud']

  @fee_aud.setter
  def fee_aud(self, value):
    self['fee_aud'] = value

  @property
  def btcusd(self):
    return self['btcusd']

  @btcusd.setter
  def btcusd(self, value):
    self['btcusd'] = value

  @property
  def btcaud(self):
    return self['btcaud']

  @btcaud.setter
  def btcaud(self, value):
    self['btcaud'] = value

  @property
  def ltcusd(self):
    return self['ltcusd']

  @ltcusd.setter
  def ltcusd(self, value):
    self['ltcusd'] = value

  @property
  def ltcbtc(self):
    return self['ltcbtc']

  @ltcbtc.setter
  def ltcbtc(self, value):
    self['ltcbtc'] = value

  @property
  def nmcusd(self):
    return self['nmcusd']

  @nmcusd.setter
  def nmcusd(self, value):
    self['nmcusd'] = value

  @property
  def ethusd(self):
    return self['ethusd']

  @ethusd.setter
  def ethusd(self, value):
    self['ethusd'] = value

  @property
  def ethbtc(self):
    return self['ethbtc']

  @ethbtc.setter
  def ethbtc(self, value):
    self['ethbtc'] = value

  @property
  def audusd(self):
    return self['audusd']

  @audusd.setter
  def audusd(self, value):
    self['audusd'] = value

  @property
  def comments(self):
    return self['comments']

  @comments.setter
  def comments(self, value):
    self['comments'] = value

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
    
  BRIEF_KEYS = ['datetime', 'operation', 'pair', 'aud', 'usd', 'volume']

  @property
  def brief(self):
    """ return a dict which contains brief information of this transaction """
    brief_keys = Transaction.BRIEF_KEYS[:-1] # exclude volume
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
    result = dict(**{my_key: self[my_key] for my_key in brief_keys})
    if volume_key:
      result.update(volume=self[volume_key])
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
    feecrypto = None
    for crypto in CRYPTOS:
      feecrypto_field = 'fee_{}'.format(crypto)
      if hasattr(tran, feecrypto_field):
        volume = getattr(tran, feecrypto_field)
        if volume > 0:
          feecrypto = crypto
          break
    if not feecrypto:
      raise Exception('Cannot find crypto fee in transaction')
    mocked.pair = '{}{}'.format(feecrypto, DEFAULT_FIAT)
    return mocked

  def can_combine(self, trans):
    """ can combine """
    return trans.operation in ['buy', 'sell'] and \
      self.exchange == trans.exchange and \
      self.operation == trans.operation and \
        self.pair == trans.pair and \
      (trans.datetime - self.datetime).total_seconds() < 30

  def combine(self, trans):
    """ combine two trans """
    if not self.can_combine(trans):
      raise Exception('Cannot combine')
    self.btc += trans.btc
    self.ltc += trans.ltc
    self.nmc += trans.nmc
    self.eth += trans.eth
    self.usd += trans.usd
    self.aud += trans.aud
    self.fee_btc += trans.fee_btc
    self.fee_usd += trans.fee_usd
    self.fee_aud += trans.fee_aud
    if self.btc + trans.btc > 0:
      if 'btcaud' in self and 'btcaud' in trans:
        self.btcaud = (self.btcaud * self.btc + trans.btcaud * trans.btc) / (
            self.btc + trans.btc)
      if 'btcusd' in self and 'btc' in trans:
        self.btcusd = (self.btcusd * self.btc + trans.btcusd * trans.btc) / (
            self.btc + trans.btc)
    if self.ltc + trans.ltc > 0:
      if 'ltcusd' in self and 'ltcusd' in trans:
        self.ltcusd = (self.ltcusd * self.ltc + trans.ltcusd * trans.ltc) / (
            self.ltc + trans.ltc)
      if 'ltcbtc' in self and 'ltcbtc' in trans:
        self.ltcbtc = (self.ltcbtc * self.ltc + trans.ltcbtc * trans.ltc) / (
            self.ltc + trans.ltc)
    if self.nmc + trans.nmc > 0:
      if 'nmcusd' in self and 'nmcusd' in trans:
        self.nmcusd = (self.nmcusd * self.nmc + trans.nmcusd * trans.nmc) / (
            self.nmc + trans.nmc)
    if self.eth + trans.eth > 0:
      if 'ethusd' in self and 'ethusd' in trans:
        self.ethusd = (self.ethusd * self.eth + trans.ethusd * trans.eth) / (
            self.eth + trans.eth)
      if 'ethbtc' in self and 'ethbtc' in trans:
        self.ethbtc = (self.ethbtc * self.eth + trans.ethbtc * trans.eth) / (
            self.eth + trans.eth)
    if self.audusd > 0 and trans.audusd > 0:
      self.audusd = (self.audusd + trans.audusd) / 2.
