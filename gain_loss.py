import copy
from position import Position
from transaction import Transaction
from shared_def import LOCALE_FIAT

class GainLoss(dict):
  def __init__(self):
    super(GainLoss, self).__init__()
    self.fiat = 0
    self.left_date = self.right_date = None
    self.position = None
    self.transaction = None
    self.matched = 0
    self.description = ''

  @property
  def discountable(self):
    return (self.fiat > 0 and (self.right_date - self.left_date).days > 365)

  @property
  def fiat(self):
    """ Gain or loss amount in local fiat currency """
    return self['fiat']

  @fiat.setter
  def fiat(self, value):
    self['fiat'] = value

  @property
  def gain(self):
    return self.fiat >= 0

  @property
  def transaction(self):
    return self['transaction']

  @transaction.setter
  def transaction(self, value):
    self['transaction'] = copy.deepcopy(value)

  @property
  def position(self):
    return self['position']

  @position.setter
  def position(self, value):
    self['position'] = copy.deepcopy(value)

  @property
  def left_date(self):
    return self['left_date']

  @left_date.setter
  def left_date(self, value):
    self['left_date'] = value

  @property
  def right_date(self):
    return self['right_date']

  @right_date.setter
  def right_date(self, value):
    self['right_date'] = value

  @property
  def description(self):
    return self['description']

  @description.setter
  def description(self, value):
    self['description'] = value

  @property
  def matched(self):
    return self['matched']

  @matched.setter
  def matched(self, value):
    self['matched'] = value

  @property
  def brief(self):
    locale_fiat_lower = LOCALE_FIAT.lower()
    return dict(
        **{locale_fiat_lower: self.fiat},
        position=self.position.brief,
        buy_transaction=self.position.transaction.brief,
        sell_transaction=self.transaction.brief)

  @property
  def brief_csv(self):
    position = self.position.brief if self.position else Position.create_na_brief()
    buy_transaction = self.position.transaction.brief if self.position else Transaction.create_na_brief()
    sell_transaction = self.transaction.brief if self.transaction else Transaction.create_na_brief()
    locale_fiat_lower = LOCALE_FIAT.lower()
    row = [
        '{}'.format('gain' if self.gain else 'loss'),  # gain_or_loss
        '{}'.format(self.right_date), # datetime
        '{}'.format(self.fiat),  # fiat amount
        '{}'.format('Yes' if self.discountable else 'No' if self.
                    gain else 'N/A'),  # discountable
        '{}'.format(self.description),  # description
        '{}'.format(buy_transaction.get(locale_fiat_lower, 'N/A')),  # buy_transaction.fiat
        '{}'.format(buy_transaction['volume']),  # buy_transaction.volume
        '{}'.format(buy_transaction['datetime']),  # buy_transaction.datetime
        '{}'.format(buy_transaction['operation']),  # buy_transaction.operation
        '{}'.format(buy_transaction['pair']),  # buy_transaction.pair
        '{}'.format(buy_transaction['usd']),  # buy_transaction.usd
        '{}'.format(position['asset']),  # position.asset
        '{}'.format(position.get(locale_fiat_lower, 'N/A')),  # position.fiat (uses locale-specific key)
        '{}'.format(position['initial_volume']),  # position.initial_volume
        '{}'.format(position['price']),  # position.price
        '{}'.format(position['volume']),  # position.volume
        '{}'.format(self.matched),  # matched
        '{}'.format(sell_transaction.get(locale_fiat_lower, 'N/A')),  # sell_transaction.fiat
        '{}'.format(sell_transaction['volume']),  # sell_transaction.volume
        '{}'.format(sell_transaction['datetime']),  # sell_transaction.datetime
        '{}'.format(
            sell_transaction['operation']),  # sell_transaction.operation
        '{}'.format(sell_transaction['pair']),  # sell_transaction.pair
        '{}'.format(sell_transaction['usd'])  # sell_transaction.usd
    ]

    return ','.join(row)
