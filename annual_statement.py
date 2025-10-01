import pprint
from shared_def import CRYPTOS
from portfolio import Portfolio
from gain_loss import GainLoss

pp = pprint.PrettyPrinter(indent=2, width=100, compact=True)


class AnnualStatement(dict):
  """ 
  Annual statement for a financial year, the end result for tax return of the year
  Contains portfolio at the end of the year, all gains and losses during the year
  """
  def __init__(self, financial_year, portfolio=None, losses=None):
    super(AnnualStatement, self).__init__()
    self.financial_year = financial_year
    self.portfolio = portfolio if portfolio else Portfolio()
    self.gains = []
    self.losses = []
    if losses:
      self.losses.extend(losses)
      self.previous_year_loss = losses[0]
    else:
      self.previous_year_loss = None
    self.transactions = []
    self.feeloss = None

  @property
  def previous_year_loss(self):
    return self['previous_year_loss']

  @previous_year_loss.setter
  def previous_year_loss(self, value):
    self['previous_year_loss'] = value

  @property
  def financial_year(self):
    return self['financial_year']

  @financial_year.setter
  def financial_year(self, value):
    self['financial_year'] = value

  @property
  def portfolio(self):
    return self['portfolio']

  @portfolio.setter
  def portfolio(self, value):
    self['portfolio'] = value

  @property
  def gains(self):
    return self['gains']

  @gains.setter
  def gains(self, value):
    self['gains'] = value

  @property
  def losses(self):
    return self['losses']

  @losses.setter
  def losses(self, value):
    self['losses'] = value

  def process_transaction(self, tran):
    self.transactions.append(tran)
    if tran.operation in ['buy', 'sell']:
      gains, losses = self.portfolio.process_transaction(tran)
      if gains:
        self.gains.extend(gains)
      if losses:
        self.losses.extend(losses)
    elif tran.operation in ['deposit', 'withdrawal']:
      for crypto in CRYPTOS:
        feefield = 'fee_{}'.format(crypto.lower())
        if hasattr(tran, feefield):
          volume = getattr(tran, feefield)
          if volume > 0:
            self.portfolio.dispose_without_tax_event(crypto, volume)
            break
    elif tran.operation == 'loss':
      for crypto in CRYPTOS:
        cryptofield = crypto.lower()
        if hasattr(tran, cryptofield):
          volume = getattr(tran, cryptofield)
          if volume > 0:
            self.losses.extend(self.portfolio.dispose_as_loss(crypto, tran))
            break
      else:
        # Arbitrary AUD loss
        loss = GainLoss()
        loss.aud = -abs(tran.aud)
        loss.description = 'Arbitrary loss because of: ' + tran.comments
        loss.left_date = loss.right_date = None
        self.losses.append(loss)
    else:
      raise Exception('Unexpected transaction')

  @property
  def gross_gains_sum(self):
    return sum([item.aud for item in self.gains], 0)

  @property
  def non_discountable_gains_sum(self):
    return sum([item.aud for item in self.gains if not item.discountable], 0)

  @property
  def discountable_gains_sum(self):
    return sum([item.aud for item in self.gains if item.discountable], 0)

  @property
  def taxable_gains_sum(self):
    return self.discountable_gains_sum / 2. + self.non_discountable_gains_sum

  @property
  def this_year_losses(self):
    return self.losses_sum - (self.previous_year_loss.aud
                              if self.previous_year_loss else 0)

  @property
  def losses_sum(self):
    return sum([item.aud for item in self.losses], 0)

  @property
  def net_gain(self):
    return self.taxable_gains_sum + self.losses_sum

  @property
  def carried_losses(self):
    if self.net_gain < 0:
      gl = GainLoss()
      gl.aud = self.net_gain
      return [gl]
    else:
      return None

  def create_fee_loss(self):
    if self.feeloss:
      raise Exception('Fee loss cannot be created more than once')
    self.feeloss = GainLoss()
    self.feeloss.aud = -abs(
        sum([item.fee_aud for item in self.transactions], 0))
    self.feeloss.description = "Loss of transaction fees"
    self.losses.append(self.feeloss)

  def report(self):
    print('========================================================')
    print('Tax return report for year: {}'.format(self.financial_year))
    print('Gross gains of the year: ${:.2f} AUD'.format(self.gross_gains_sum))
    print('Discountable gains of the year: ${:.2f} AUD'.format(
        self.discountable_gains_sum))
    print('Non-discountable gains of the year: ${:.2f} AUD'.format(
        self.non_discountable_gains_sum))
    print('Taxable gains of the year: ${:.2f} AUD'.format(
        self.taxable_gains_sum))
    print('Losses carried from previous year: - ${:.2f} AUD'.format(
        abs(self.previous_year_loss.aud if self.previous_year_loss else 0)))
    print('Losses of this year only: - ${:.2f} AUD'.format(
        abs(self.this_year_losses)))
    print('Total losses at the end of the year: - ${:.2f} AUD'.format(
        abs(self.losses_sum)))
    print('Net gains of the year: {} ${:.2f} AUD'.format(
        '-' if self.net_gain < 0 else '', abs(self.net_gain)))
    print('Portfolio of the year:')
    for crypto in CRYPTOS:
      if crypto in self.portfolio:
        print('  {}: {}'.format(
            crypto, sum([item.volume for item in self.portfolio[crypto]], 0)))
        # for position in self.portfolio[crypto]:
        #   if position.volume > 0:
        #     pp.pprint(position)
    print('========================================================')
    print('')