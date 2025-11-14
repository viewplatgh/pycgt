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

  def _dispose_position_for_gain_loss(self, position, volume, disposing_price, transaction, crypto_fee_field, gain_loss, gains, losses):
    """ Shared helper function to dispose position for gain/loss calculation """
    gain_loss.position = position
    gain_loss.left_date = position.transaction.datetime
    gain_loss.right_date = transaction.datetime
    matching = min(position.volume, volume)
    position.volume -= matching
    volume -= matching
    gain_loss.matched = matching
    gain_loss.fiat = (disposing_price - position.price) * matching
    gains.append(gain_loss) if gain_loss.gain else losses.append(gain_loss)
    print(gain_loss.brief_csv)

    incidental_loss = GainLoss()
    incidental_loss.description = 'Incidental loss because of fee paid in crypto'
    incidental_loss.transaction = transaction
    incidental_loss.transaction.volume = transaction[crypto_fee_field]
    # the full market value of crypto paid as fee is deductible as incidental loss
    incidental_loss.fiat = -abs(disposing_price * matching)
    incidental_loss.left_date = position.transaction.datetime
    incidental_loss.right_date = transaction.datetime
    losses.append(incidental_loss)
    print(incidental_loss.brief_csv)
    return volume

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
          gl.fiat = (tran.fiat / tran[crypto] - item.price) * matching
          gains.append(gl) if gl.gain else losses.append(gl)
          print(gl.brief_csv)
          if disposed_volume < PRECISION_THRESHOLD:
            break
      if disposed_volume > PRECISION_THRESHOLD:
        raise Exception('Unexpected, disposing position not existing')
      
      # deal with fees paid in either crypto or fiat
      fiat_fee_field = 'fee_{}'.format(LOCALE_FIAT.lower())
      fee_fiat = tran[fiat_fee_field] if fiat_fee_field in tran and tran[fiat_fee_field] > 0 else 0
      # assuming the crypto of fee is left of the pair at first as it's the most case
      fee_crypto = tran.left2right[0]
      crypto_fee_field = 'fee_{}'.format(fee_crypto.lower()) 
      if not (crypto_fee_field in tran and tran[crypto_fee_field] > 0):
        # try to find crypto fees paid in other cryptos
        OTHER_CRYPTOS = [item for item in CRYPTOS if item != tran.left2right[0]]
        for item_crypto in OTHER_CRYPTOS:
          fee_crypto = item_crypto
          crypto_fee_field = 'fee_{}'.format(item_crypto.lower())
          if crypto_fee_field in tran and tran[crypto_fee_field] > 0:
            break
      if crypto_fee_field in tran and tran[crypto_fee_field] > 0:
        volume = tran[crypto_fee_field]
        crypto_fiat_rate_field = '{}{}'.format(fee_crypto, LOCALE_FIAT).lower()
        disposing_price = tran[crypto_fiat_rate_field] if crypto_fiat_rate_field in tran and tran[crypto_fiat_rate_field] > 0 else (fee_fiat / volume)
        # go through positions list of the crypto to dispose, from 0 to end
        for item in self[fee_crypto]:
          if item.volume > 0:
            gl = GainLoss()
            gl.transaction = tran
            # make up a sell(crypto_fee) transaction based on original transaction
            gl.transaction.volume = tran[crypto_fee_field]
            gl.transaction[fee_crypto] = tran[crypto_fee_field]
            gl.transaction[LOCALE_FIAT.lower()] = fee_fiat if fee_fiat > 0 else disposing_price * tran[crypto_fee_field]
            gl.transaction[crypto_fee_field] = gl.transaction[fiat_fee_field] = 0
            gl.transaction.operation = 'sell'
            gl.transaction.pair = '{}{}'.format(fee_crypto, LOCALE_FIAT).lower()

            volume = self._dispose_position_for_gain_loss(item, volume, disposing_price, tran, crypto_fee_field, gl, gains,losses)
            if volume < PRECISION_THRESHOLD:
              break
        if volume > PRECISION_THRESHOLD:
          raise Exception('Unexpected, disposing position not existing')
      elif fee_fiat > 0:
        # simply treat position fee of fiat as incidental loss as no crypto fee information
        incidental_loss = GainLoss()
        incidental_loss.description = 'Incidental loss because of fee paid in fiat only'
        incidental_loss.transaction = tran
        incidental_loss.left_date = incidental_loss.right_date = tran.datetime
        incidental_loss.fiat = -abs(fee_fiat)
        losses.append(incidental_loss)
        print(incidental_loss.brief_csv)

      return gains, losses

    if tran.left2right[1] not in CRYPTOS:
      # neither left nor right is crypto, skip with logging
      logger.warning('Skipped non crypto trading, left2right:{}'.format(tran.left2right))
    return (None, None)
  
  def process_fees_incurred_transactions(self, tran):
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
              
              volume = self._dispose_position_for_gain_loss(item, volume, disposing_price, tran, crypto_fee_field, gl, gains,losses)
              if volume < PRECISION_THRESHOLD:
                break
          if volume > PRECISION_THRESHOLD:
            raise Exception('Unexpected, disposing position not existing')
          return gains, losses
    
    if fee_fiat > 0:
      # no fee paid in crypto, just create loss based on fee_fiat
      incidental_loss = GainLoss()
      incidental_loss.description = 'Incidental loss because of fee paid in fiat'
      incidental_loss.transaction = tran
      incidental_loss.fiat = -abs(fee_fiat)
      incidental_loss.left_date = incidental_loss.right_date = tran.datetime
      print(incidental_loss.brief_csv)
      return (None, [incidental_loss])
    
    logger.info('Skipped transaction: {}, as nothing detected to process'.format(tran.brief))
    return (None, None)

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
        gl.fiat = -matching * item.price
        losses.append(gl)
        print(gl.brief_csv)
        if disposed_volume < PRECISION_THRESHOLD:
          break
    if disposed_volume > PRECISION_THRESHOLD:
      raise Exception('Unexpected, disposing position not existing')
    return losses
