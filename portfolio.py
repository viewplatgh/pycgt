import pprint
from shared_def import CRYPTOS, POSITION_ACCOUNTING
from gain_loss import GainLoss
from position import Position
from transaction import Transaction

pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)


class Portfolio(dict):
  """ 
  Portfolio contains all positions of all cryptos
  It's a dict with key as crypto name, value as list of Position
  """
  def __init__(self):
    super(Portfolio, self).__init__()
    for item in CRYPTOS:
      self[item] = []

  def process_buy_sell_transaction(self, tran):
    """ Will either generate portfolio or tax capital gain/loss """
    if tran.left2right[1] in CRYPTOS:
      # the list of position will be processed from 0 to end
      # so append will be FIFO, insert will be FILO
      if POSITION_ACCOUNTING == 'fifo':
        self[tran.left2right[1]].append(Position(tran))
      elif POSITION_ACCOUNTING == 'filo':
        self[tran.left2right[1]].insert(0, Position(tran))

    if tran.left2right[0] in CRYPTOS:
      # crypto disposal happened
      gains = []
      losses = []
      crypto = tran.left2right[0]
      disposed_volume = tran[crypto]

      # go through positions list of the crypto to dispose, from 0 to end
      for item in self[crypto]:
        if item.volume > 0:
          gl = GainLoss()
          gl.transaction = tran
          gl.position = item
          gl.left_date = item.transaction.datetime
          gl.right_date = tran.datetime
          matching = min(item.volume, disposed_volume)
          item.volume -= matching
          disposed_volume -= matching
          gl.matched = matching
          gl.aud = (tran.aud / tran[crypto] - item.price) * matching
          gains.append(gl) if gl.gain else losses.append(gl)
          print(gl.brief_csv)
          if disposed_volume < 0.00000001:
            break
      if disposed_volume > 0.00000001:
        raise Exception('Unexpected, disposing position not existing')
      return gains, losses

    if tran.left2right[1] not in CRYPTOS:
      # neither left nor right is crypto, skip with logging
      pp.pprint('Skipped non crypto trading...')
      pp.pprint('left2right:')
      pp.pprint(tran.left2right)
      pp.pprint(tran)
    return (None, None)
  
  def process_non_buy_sell_transaction(self, tran):
    """ Handle fee paid in crypto in non buy/sell transaction
    Regard it as tax event of disposing the crypto as well
    the same as sell, will result in gain or loss
    and cost base value of the fee is regarded as loss
    return all the (gains, losses) same as process_buy_sell_transaction
    """
    fee_aud = getattr(tran, 'fee_aud')
    for crypto in CRYPTOS:
      feefield = 'fee_{}'.format(crypto.lower())
      if hasattr(tran, feefield):
        volume = getattr(tran, feefield)
        if volume > 0:
          gains = []
          losses = []
          disposing_price = fee_aud / volume
          for item in self[crypto]: # go through positions list of the crypto to dispose, from 0 to end
            if item.volume > 0:
              gl = GainLoss()
              gl.transaction = Transaction.mock_sell_transaction(tran)
              gl.position = item
              gl.left_date = item.transaction.datetime
              gl.right_date = tran.datetime
              matching = min(item.volume, volume)
              item.volume -= matching
              volume -= matching
              gl.matched = matching
              gl.aud = (disposing_price - item.price) * matching
              gains.append(gl) if gl.gain else losses.append(gl)
              print(gl.brief_csv)
              incidental_loss = GainLoss()
              incidental_loss.description = 'Incidental loss because of fee paid in crypto'
              incidental_loss.transaction = tran
              incidental_loss.aud = -abs(item.price * matching)
              losses.append(incidental_loss)
              print(incidental_loss.brief_csv)
              if volume < 0.00000001:
                break
          if volume > 0.00000001:
            raise Exception('Unexpected, disposing position not existing')
          return gains, losses
    
    # no fee paid in crypto, just create loss based on fee_aud
    incidental_loss = GainLoss()
    incidental_loss.description = 'Incidental loss because of fee paid in fiat'
    incidental_loss.transaction = tran
    incidental_loss.aud = -abs(fee_aud)
    print(incidental_loss.brief_csv)
    return (None, [incidental_loss])

  def dispose_without_tax_event(self, crypto, volume):
    for item in self[crypto]:
      if item.volume > 0:
        matching = min(item.volume, volume)
        item.volume -= matching
        volume -= matching
        if volume == 0:
          break
    if volume != 0:
      raise Exception('Failed to dispose')

  def dispose_as_loss(self, crypto, tran):
    losses = []
    disposed_volume = tran[crypto]

    for item in self[crypto]:
      if item.volume > 0:
        gl = GainLoss()
        gl.transaction = tran
        gl.position = item
        gl.left_date = item.transaction.datetime
        gl.right_date = tran.datetime
        matching = min(item.volume, disposed_volume)
        item.volume -= matching
        disposed_volume -= matching
        gl.matched = matching
        gl.aud = -matching * item.price
        losses.append(gl)
        print(gl.brief_csv)
        if disposed_volume < 0.00000001:
          break
    if disposed_volume > 0.00000001:
      raise Exception('Unexpected, disposing position not existing')
    return losses

# following code looks unnecessary, commmented out for now
# def _dict_set(dt, key, value):
#   dt[key] = value

# for item in CRYPTOS:
#   setattr(
#       Portfolio, item, lambda key: property(
#           lambda self: self[key], lambda self, value: _dict_set(
#               self, key, value))(item))
