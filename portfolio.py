import pprint
from shared_def import LOCALE_FIAT, FIATS, CRYPTOS, POSITION_ACCOUNTING, PRECISION_THRESHOLD
from gain_loss import GainLoss
from position import Position
from transaction import Transaction
from logger import logger

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
      else:
        raise Exception('Unexpected POSITION_ACCOUNTING: {}'.format(POSITION_ACCOUNTING))

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
          if disposed_volume < PRECISION_THRESHOLD:
            break
      if disposed_volume > PRECISION_THRESHOLD:
        raise Exception('Unexpected, disposing position not existing')
      
      if tran.left2right[1] in FIATS:
        # need to deal with fees of disposing crypto for fiat
        # btw, no need to handle crypto to crypto case, because in that case fee would be added to cost base
        crypto_fee_field = 'fee_{}'.format(tran.left2right[0].lower()) # assuming the crypto of fee is left of the pair
        fiat_fee_field = 'fee_{}'.format(LOCALE_FIAT.lower())
        fee_fiat = tran[fiat_fee_field] if fiat_fee_field in tran and tran[fiat_fee_field] > 0 else 0
        if crypto_fee_field in tran and tran[crypto_fee_field] > 0:
          volume = tran[crypto_fee_field]
          crypto_fiat_field = '{}{}'.format(tran.left2right[0], LOCALE_FIAT).lower()
          disposing_price = tran[crypto_fiat_field] if crypto_fiat_field in tran and tran[crypto_fiat_field] > 0 else (fee_fiat / volume)
          # go through positions list of the crypto to dispose, from 0 to end
          for item in self[crypto]:
            if item.volume > 0:
              gl = GainLoss()
              gl.transaction = tran
              # make up a sell(crypto_fee) transaction based on original transaction
              gl.transaction.volume = tran[crypto_fee_field]
              gl.transaction[crypto] = tran[crypto_fee_field]
              gl.transaction[LOCALE_FIAT.lower()] = fee_fiat
              gl.transaction[crypto_fee_field] = gl.transaction[fiat_fee_field] = 0

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
              # cost base of disposed crypto(fee) is regarded as incidental loss
              incidental_loss = GainLoss()
              incidental_loss.description = 'Incidental loss because of fee paid in crypto'
              incidental_loss.transaction = tran
              incidental_loss.transaction.volume = tran[crypto_fee_field]
              if gl.gain:
                # cost base of disposed crypto(fee) is regarded as incidental loss
                incidental_loss.aud = -abs(item.price * matching)
              else:
                # proceed is regarded as incidental loss
                incidental_loss.aud = -abs(disposing_price * matching)
              incidental_loss.left_date = item.transaction.datetime
              incidental_loss.right_date = tran.datetime
              losses.append(incidental_loss)
              print(incidental_loss.brief_csv)
              if volume < PRECISION_THRESHOLD:
                break
          if volume > PRECISION_THRESHOLD:
            raise Exception('Unexpected, disposing position not existing')
        elif fee_fiat > 0:
          # simply treat position fee of fiat as incidental loss as no crypto fee information
          incidental_loss = GainLoss()
          incidental_loss.description = 'Incidental loss because of fee paid in fiat'
          incidental_loss.transaction = tran
          incidental_loss.left_date = incidental_loss.right_date = tran.datetime
          incidental_loss.aud = -abs(fee_fiat)
          losses.append(incidental_loss)
          print(incidental_loss.brief_csv)

      return gains, losses

    if tran.left2right[1] not in CRYPTOS:
      # neither left nor right is crypto, skip with logging
      logger.warning('Skipped non crypto trading, left2right:{}'.format(tran.left2right))
    return (None, None)
  
  def process_non_buy_sell_transaction(self, tran):
    """ Handle fee paid in crypto in non buy/sell transaction
    Regard it as tax event of disposing the crypto as well
    the same as sell, will result in gain or loss
    and cost base value of the fee is regarded as loss
    return all the (gains, losses) same as process_buy_sell_transaction
    """
    fiat_fee_field = 'fee_{}'.format(LOCALE_FIAT.lower())
    fee_fiat = getattr(tran, fiat_fee_field, 0)
    for crypto in CRYPTOS:
      crypto_fee_field = 'fee_{}'.format(crypto.lower())
      if crypto_fee_field in tran:
        volume = tran[crypto_fee_field]
        if volume > 0:
          gains = []
          losses = []
          crypto_fiat_field = '{}{}'.format(crypto, LOCALE_FIAT).lower()
          disposing_price = tran[crypto_fiat_field] if crypto_fiat_field in tran and tran[crypto_fiat_field] > 0 else (fee_fiat / volume)
          # go through positions list of the crypto to dispose, from 0 to end
          for item in self[crypto]:
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
              incidental_loss.transaction.volume = tran[crypto_fee_field]
              if gl.gain:
                # cost base of disposed crypto(fee) is regarded as incidental loss
                incidental_loss.aud = -abs(item.price * matching)
              else:
                # proceed is regarded as incidental loss
                incidental_loss.aud = -abs(disposing_price * matching)
              incidental_loss.left_date = item.transaction.datetime
              incidental_loss.right_date = tran.datetime
              losses.append(incidental_loss)
              print(incidental_loss.brief_csv)
              if volume < PRECISION_THRESHOLD:
                break
          if volume > PRECISION_THRESHOLD:
            raise Exception('Unexpected, disposing position not existing')
          return gains, losses
    
    # no fee paid in crypto, just create loss based on fee_fiat
    incidental_loss = GainLoss()
    incidental_loss.description = 'Incidental loss because of fee paid in fiat'
    incidental_loss.transaction = tran
    incidental_loss.aud = -abs(fee_fiat)
    incidental_loss.left_date = incidental_loss.right_date = tran.datetime
    print(incidental_loss.brief_csv)
    return (None, [incidental_loss])

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
        if disposed_volume < PRECISION_THRESHOLD:
          break
    if disposed_volume > PRECISION_THRESHOLD:
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
