import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m4_loss.rules import allocate
from app.modules.m3_split.rules import split
from app.modules.m2_tariffs.rules import tariffs,DEFAULT_TARIFFS
def rec(id,kind,energy,station='S'):return dict(id=id,station=station,kind=kind,energy=D(energy),start=instant('2026-11-16T00:00:00Z'),end=instant('2026-11-17T00:00:00Z'))
RATES=tariffs(DEFAULT_TARIFFS)
def order_segments(rows):
    segs=[]
    for row in rows:
        if row['kind']=='order':
            for seg in split(row,RATES):seg.setdefault('loss_kwh',D(0))
            segs.extend(split(row,RATES))
    return segs

def test_loss_proportion():
    rows=[rec('1','order','10'),rec('2','order','20'),rec('3','station','33')]
    x,b,p=allocate(rows,order_segments(rows),RATES)
    assert [r['loss_kwh'].quantize(D('0.000000001')) for r in x]==[D(1),D(2)]
    assert sum(r['loss_kwh'] for r in x)==3 and b[0]['loss_kwh']==3

def test_negative_loss_blocked():
    rows=[rec('1','order','10'),rec('2','station','9')]
    x,b,p=allocate(rows,order_segments(rows),RATES)
    assert x[0]['loss_kwh']==0 and b[0]['state']!='通过'

def test_no_meter():
    assert allocate([rec('1','order','10')])[1][0]['state']!='通过'

def test_zero_orders():
    assert allocate([rec('1','station','10')])[1][0]['state']=='无订单承接损耗'

def test_real_three_stations(raw):
    assert len(run(raw,stop=4,persist=False)['loss_balances'])==3

def test_real_loss_conserved(raw):
    x=run(raw,stop=4,persist=False)
    g=D('0.000000001')
    for station in {b['station'] for b in x['loss_balances']}:
        seg=sum(D(s.get('loss_kwh',0)) for s in x['segments'] if s['station']==station)
        bal=sum(D(b['loss_kwh']) for b in x['loss_balances'] if b['station']==station)
        ord_=sum(D(o['loss_kwh']) for o in x['orders'] if o['station']==station)
        assert seg.quantize(g)==bal.quantize(g)==ord_.quantize(g)

def test_clean_sample_has_covered_station_meters():
    from app.config import SAMPLES
    result=run((SAMPLES/'clean.csv').read_bytes(),stop=4,persist=False)
    assert result['input_count']==43 and not result['quarantine']
    assert len(result['loss_balances'])==3
    assert all(r['state']=='通过' for r in result['loss_balances'])


def test_meter_must_cover_order_interval():
    order=rec('1','order','10');meter=rec('2','station','11')
    meter['end']=instant('2026-11-16T12:00:00Z')
    rows=[order,meter]
    assigned,balances,periods=allocate(rows,order_segments(rows),RATES)
    assert balances[0]['state']=='总表未覆盖订单区间'
    assert assigned[0]['loss_kwh']==0

def test_period_evidence_keys_are_unique_per_station_slot(raw):
    x=run(raw,stop=4,persist=False)
    keys=[(p['station'],p['day'],p['slot_a']) for p in x['period_rows']]
    assert len(keys)==len(set(keys))
    assert all('label' in p and 'meter_kwh' in p and 'order_kwh' in p for p in x['period_rows'])

def test_slot_loss_follows_segments():
    # One valley order and one flat order; every occupied slot carries positive loss allocated to its segments.
    valley=dict(id='v',station='S',order='V',kind='order',energy=D(10),
                start=instant('2026-11-16T00:00:00+08:00'),end=instant('2026-11-16T01:00:00+08:00'))
    flat=dict(id='f',station='S',order='F',kind='order',energy=D(10),
              start=instant('2026-11-16T08:00:00+08:00'),end=instant('2026-11-16T09:00:00+08:00'))
    meter=dict(id='m',station='S',order='',kind='station',energy=D(26),
               start=instant('2026-11-16T00:00:00+08:00'),end=instant('2026-11-17T00:00:00+08:00'))
    rows=[valley,flat,meter]
    segs=[]
    for r in rows:
        if r['kind']=='order':segs.extend(split(r,RATES))
    assigned,balances,periods=allocate(rows,segs,RATES)
    assert balances[0]['state']=='通过'
    occupied=[p for p in periods if p['state']=='通过']
    # The flat hourly slot occupied by the flat order is above its order energy.
    assert any(p['label']=='平' and p['loss_kwh']>0 for p in occupied)
    # The valley slot has no meter headroom, so its period anomaly is surfaced as evidence.
    assert any(p['label']=='谷' and p['state']!='通过' for p in periods)
    # Total station loss (6 kWh) is conserved across order shares regardless of unattended periods.
    assert sum(r['loss_kwh'] for r in assigned)==6
    assert sum(D(s.get('loss_kwh',0)) for s in segs)==6
