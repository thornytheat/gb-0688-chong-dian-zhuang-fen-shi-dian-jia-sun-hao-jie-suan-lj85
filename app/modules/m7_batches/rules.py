from app.errors import DomainError
from decimal import Decimal as D
# Meter readings are never finer than Wh; 1e-9 kWh gives six guard digits for chained division tails.
GUARD=D('0.000000001')
def _q(value):
    return value.quantize(GUARD)
def summary(records,bad,total,segments,balances,charges,period_rows=None,orders=None):
    if len(records)+len(bad)!=total:raise DomainError('INCOMPLETE','计量行数不守恒')
    measured=sum((r['energy'] for r in records if r['kind']=='order'),D(0));split=sum((r['kwh'] for r in segments),D(0))
    if measured!=split:raise DomainError('INCOMPLETE','分时电量不守恒')
    if period_rows is not None:
        # Compare within each station at a guarded scale to absorb Decimal division tails.
        stations={r['station'] for r in balances}
        for station in sorted(stations):
            seg_loss=sum((r.get('loss_kwh',D(0)) for r in segments if r['station']==station),D(0))
            bal_loss=sum((r['loss_kwh'] for r in balances if r['station']==station),D(0))
            if _q(seg_loss)!=_q(bal_loss):raise DomainError('INCOMPLETE','分时损耗不守恒')
            if orders is not None:
                ord_loss=sum((r['loss_kwh'] for r in orders if r['station']==station),D(0))
                if _q(ord_loss)!=_q(bal_loss):raise DomainError('INCOMPLETE','订单损耗份额不守恒')
    return {'input':total,'retained':len(records),'isolated':len(bad),'measured_kwh':measured,'split_kwh':split,
            'amount':sum((r['amount'] for r in charges),D(0)),'blocked_stations':sum(r['state']!='通过' for r in balances),
            'period_anomaly':sum(r.get('period_anomaly',0) for r in balances),
            'unallocated_kwh':sum((r.get('unallocated_kwh',D(0)) for r in balances),D(0))}
