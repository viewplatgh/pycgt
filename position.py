import copy


class Position(dict):
  def __init__(self, transaction):
    super(Position, self).__init__()
    self.transaction = copy.deepcopy(transaction) # backup initial transaction for brief
    self.asset = self.transaction.left2right[1]
    self.aud = self.transaction.aud + self.transaction.fee_aud # include fee in cost base
    self.volume = self.transaction[self.asset]
    if self.volume == 0:
      raise AssertionError('Zero volume is not valid')
    self['initial_volume'] = self.volume # backup initial volume
    self.price = self.aud / self.volume # cost price

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
  def aud(self):
    return self['aud']

  @aud.setter
  def aud(self, value):
    self['aud'] = value

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

  @property
  def brief(self):
    return dict(
        **{
            my_key: self[my_key]
            for my_key in
            ['asset', 'aud', 'volume', 'price', 'initial_volume']
        })
