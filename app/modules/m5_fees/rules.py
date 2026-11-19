from decimal import Decimal as D,ROUND_HALF_UP,ROUND_FLOOR
from collections import defaultdict
def charges(orders,segments,loss_rate):
    fees=defaultdict(lambda:D(0))
    period_lines=defaultdict(list)
    for row in segments:
        rate=row.get('rate',D(0))
        fees[row['id']]+=row['fee']
        loss=row.get('loss_kwh',D(0))
        gross=row['fee']+loss*loss_rate
        kwh=row.get('kwh')
        gross_rate=(rate+loss*loss_rate/kwh) if kwh and kwh>0 else None
        period_lines[row['id']].append({'order':row.get('order',''),'station':row.get('station',''),
            'day':row.get('day',''),'slot_a':row.get('slot_a'),'slot_b':row.get('slot_b'),
            'label':row.get('label',''),'start':row.get('start'),'end':row.get('end'),
            'kwh':kwh,'rate':rate,'loss_kwh':loss,'loss_rate':loss_rate,
            'raw_fee':gross,'gross_rate':gross_rate})
    by_station=defaultdict(list)
    for row in orders:
        raw_amount=fees[row['id']]+row['loss_kwh']*loss_rate
        by_station[row['station']].append({**row,'raw_amount':raw_amount,'periods':period_lines.get(row['id'],[])})
    result=[]
    for station,group in sorted(by_station.items()):
        target=sum((r['raw_amount'] for r in group),D(0)).quantize(D('.01'),rounding=ROUND_HALF_UP)
        amounts=[r['raw_amount'].quantize(D('.01'),rounding=ROUND_FLOOR) for r in group]
        pennies=int((target-sum(amounts,D(0)))/D('.01'));order=sorted(range(len(group)),key=lambda i:(-(group[i]['raw_amount']-amounts[i]),group[i]['id']))
        for i in order[:pennies]:amounts[i]+=D('.01')
        result.extend({**row,'amount':amounts[i],'state':row['loss_state']} for i,row in enumerate(group))
    return result
