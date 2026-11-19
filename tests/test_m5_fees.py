import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m5_fees.rules import charges
def o(id):return dict(id=id,station='S',loss_kwh=D(0),loss_state='通过')

def test_pennies_conserved():
    # TRAP-24
    x=charges([o('1'),o('2'),o('3')],[{'id':str(i),'fee':D('.005')} for i in range(1,4)],D(0));assert sum(r['amount'] for r in x)==D('.02')

def test_decimal_exact():
    # TRAP-10
    x=charges([o('1')],[{'id':'1','fee':D('.1')} for _ in range(1000)],D(0));assert x[0]['amount']==100

def test_loss_fee():
    x=o('1');x['loss_kwh']=D(2);assert charges([x],[],D('.65'))[0]['amount']==D('1.30')

def test_empty():
    assert charges([],[],D(1))==[]

def test_real_currency_scale(raw):
    assert all(D(x['amount']).as_tuple().exponent==-2 for x in run(raw,stop=5,persist=False)['charges'])

def test_real_count(raw):
    assert len(run(raw,stop=5,persist=False)['charges'])==40

def test_real_positive_fee(raw):
    assert all(D(x['amount'])>0 for x in run(raw,stop=5,persist=False)['charges'])

def test_period_gross_rate_is_exact():
    # One 10 kWh flat segment carrying 2 kWh loss: gross rate = 0.75 + 2*0.65/10 = 0.88.
    seg={'id':'1','fee':D('7.5'),'rate':D('0.75'),'kwh':D(10),'loss_kwh':D(2)}
    x=charges([o('1')],[seg],D('.65'))
    line=x[0]['periods'][0]
    assert line['gross_rate']==D('0.88')
    assert line['raw_fee']==D('8.80')

def test_every_order_has_unique_period_settlement(raw):
    x=run(raw,stop=5,persist=False)
    for charge in x['charges']:
        assert charge['periods']
        keys=[(p['day'],p['slot_a'],str(p['start']),str(p['end'])) for p in charge['periods']]
        assert len(keys)==len(set(keys))
        # Period money re-aggregates to the order's unrounded amount (guarded against division tails).
        got=sum(D(p['raw_fee']) for p in charge['periods'])
        assert abs(got-D(charge['raw_amount']))<D('0.000000001')

def test_station_payable_equals_order_shares(raw):
    x=run(raw,stop=5,persist=False)
    # Largest-remainder pennies guarantee the rounded station total equals the rounded order-share sum.
    for station in {c['station'] for c in x['charges']}:
        shares=sum(D(c['amount']) for c in x['charges'] if c['station']==station)
        raw_total=sum(D(c['raw_amount']) for c in x['charges'] if c['station']==station)
        assert shares==raw_total.quantize(D('.01'))

