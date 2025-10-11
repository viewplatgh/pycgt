import copy
from shared_def import LOCALE_FIAT


class Position(dict):
  def __init__(self, transaction):
    super(Position, self).__init__()
    self.transaction = copy.deepcopy(transaction) # backup initial transaction for brief
    self.asset = self.transaction.left2right[1]
    # Use LOCALE_FIAT to get fiat field dynamically
    locale_fiat_lower = LOCALE_FIAT.lower()
    fee_field = 'fee_{}'.format(locale_fiat_lower)
    fiat_amount = self.transaction[locale_fiat_lower] + self.transaction[fee_field] # include fee in cost base
    self.fiat = fiat_amount
    self.volume = self.transaction[self.asset]
    if self.volume == 0:
      raise AssertionError('Zero volume is not valid')
    self['initial_volume'] = self.volume # backup initial volume
    self.price = fiat_amount / self.volume # cost price

  @property
  def asset(self):
    return self['asset']

  @asset.setter
  def asset(self, value):
    self['asset'] = value

  @property
  def transaction(self):
    return self['transaction']

  @transaction.setter
  def transaction(self, value):
    self['transaction'] = copy.deepcopy(value)

  @property
  def fiat(self):
    """Returns the fiat amount based on LOCALE_FIAT configuration"""
    return self[LOCALE_FIAT.lower()]

  @fiat.setter
  def fiat(self, value):
    self[LOCALE_FIAT.lower()] = value

  @property
  def volume(self):
    return self['volume']

  @volume.setter
  def volume(self, value):
    self['volume'] = value

  @property
  def price(self):
    return self['price']

  @price.setter
  def price(self, value):
    self['price'] = value

  @property
  def initial_volume(self):
    return self['initial_volume']

  BRIEF_KEYS = ['asset', LOCALE_FIAT.lower(), 'volume', 'price', 'initial_volume']

  @property
  def brief(self):
    return dict(
        **{
            my_key: self[my_key]
            for my_key in
            Position.BRIEF_KEYS
        })

  @staticmethod
  def create_na_brief():
    return dict(
        **{
            my_key: 'N/A'
            for my_key in
            Position.BRIEF_KEYS
        })
