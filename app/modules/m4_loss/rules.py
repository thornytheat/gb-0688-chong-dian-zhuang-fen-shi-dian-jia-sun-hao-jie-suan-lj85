from decimal import Decimal as D, localcontext
from collections import defaultdict
from app.modules.m3_split.rules import split, slot_label

def _period_key(seg):
    return seg['day'],seg['slot_a']

def allocate(rows, segments=None, tariffs=None):
    # Loss divisions can chain across periods; wider precision keeps the tail fixes exact.
    with localcontext() as ctx_dec:
        ctx_dec.prec=40
        return _allocate(rows,segments,tariffs)

def _allocate(rows, segments, tariffs):
    stations=defaultdict(list)
    for row in rows:stations[row['station']].append(row)
    assigned=[];balances=[];period_rows=[]
    meter_segments=[]
    if segments is not None and tariffs is not None:
        for row in rows:
            if row['kind']!='station':continue
            try:meter_segments.extend(split(row,tariffs))
            except Exception:pass
    seg_by_station=defaultdict(list)
    if segments is not None:
        for seg in segments:seg_by_station[seg['station']].append(seg)
    for station,group in sorted(stations.items()):
        orders=[r for r in group if r['kind']=='order'];meters=[r for r in group if r['kind']=='station']
        consumed=sum((r['energy'] for r in orders),D(0));meter=sum((r['energy'] for r in meters),D(0));loss=meter-consumed
        state='通过'
        if len(meters)!=1:state='总表缺失或重复'
        elif any(r['start']<meters[0]['start'] or r['end']>meters[0]['end'] for r in orders):state='总表未覆盖订单区间'
        elif loss<0:state='订单电量超过总表'
        elif consumed==0 and loss>0:state='无订单承接损耗'
        shares=[D(0) for _ in orders]
        period_anomaly=0;unallocated=D(0);periods=[]
        if state=='通过' and consumed>0:
            local_segs=sorted(seg_by_station.get(station,[]),key=lambda s:(s['id'],s['start']))
            meter_by=defaultdict(lambda:D(0));order_by=defaultdict(lambda:D(0));rate_by={}
            for seg in local_segs:
                key=_period_key(seg);order_by[key]+=seg['kwh'];rate_by[key]=seg['rate']
            for seg in meter_segments:
                if seg['station']!=station:continue
                key=_period_key(seg);meter_by[key]+=seg['kwh'];rate_by.setdefault(key,seg['rate'])
            slot_loss=defaultdict(lambda:D(0));slot_state={}
            for key in sorted(set(meter_by)|set(order_by)):
                m=meter_by.get(key,D(0));c=order_by.get(key,D(0));slot=m-c
                if slot<0:
                    slot_state[key]='时段订单电量超过总表';period_anomaly+=1;unallocated+=slot
                elif c==0 and m>0:
                    slot_state[key]='时段无订单承接损耗';period_anomaly+=1;unallocated+=slot
                else:
                    slot_state[key]='通过';slot_loss[key]=slot
                day,a=key
                periods.append({'station':station,'day':day,'slot_a':a,'slot_b':_slot_b(local_segs,meter_segments,key),
                                'label':slot_label(rate_by[key]) if key in rate_by else '',
                                'rate':rate_by.get(key),'meter_kwh':m,'order_kwh':c,'loss_kwh':slot,'state':slot_state[key]})
            # Level 1: each meter period's loss follows the order segments inside that same period.
            for key,slot in slot_loss.items():
                if not slot:continue
                members=[seg for seg in local_segs if _period_key(seg)==key]
                partials=[slot*seg['kwh']/order_by[key] for seg in members]
                partials[-1]+=slot-sum(partials,D(0))
                for seg,part in zip(members,partials):
                    seg['loss_kwh']=seg.get('loss_kwh',D(0))+part
            # Level 2: residual pool (negative-slot gaps and unattended periods) by order energy share.
            residual=loss-sum(slot_loss.values(),D(0))
            if residual:
                partials=[residual*r['energy']/consumed for r in orders]
                partials[-1]+=residual-sum(partials,D(0))
                # Carry each order's residual onto its own segments so period evidence conserves the station loss.
                for row,part in zip(orders,partials):
                    own=[seg for seg in local_segs if seg['id']==row['id']]
                    if not own:continue
                    bits=[part*seg['kwh']/row['energy'] for seg in own]
                    bits[-1]+=part-sum(bits,D(0))
                    for seg,bit in zip(own,bits):
                        seg['loss_kwh']=seg.get('loss_kwh',D(0))+bit
            # Station-level tail fix: force the final segment so the station loss is conserved exactly.
            tail=loss-sum((s.get('loss_kwh',D(0)) for s in local_segs),D(0))
            if tail and local_segs:
                local_segs[-1]['loss_kwh']=local_segs[-1].get('loss_kwh',D(0))+tail
        # Order shares are exactly the sum of their segment-level losses, then the last order is forced
        # to absorb any rounding remainder so order shares, segments and the meter loss are all identical.
        for i,row in enumerate(orders):
            shares[i]=sum((s.get('loss_kwh',D(0)) for s in local_segs if s['id']==row['id']),D(0)) if state=='通过' and consumed>0 else D(0)
        if state=='通过' and consumed>0 and orders:
            shares[-1]+=loss-sum(shares,D(0))
        for i,row in enumerate(orders):
            assigned.append({**row,'loss_kwh':shares[i] if i<len(shares) else D(0),'loss_state':state})
        balances.append({'station':station,'meter_kwh':meter,'order_kwh':consumed,'loss_kwh':loss,'state':state,
                         'periods':len(periods),'period_anomaly':period_anomaly,'unallocated_kwh':unallocated})
        period_rows.extend(periods)
    return assigned,balances,period_rows

def _slot_b(local_segs,meter_segments,key):
    for seg in list(local_segs)+list(meter_segments):
        if _period_key(seg)==key:return seg['slot_b']
    return key[1]+1
