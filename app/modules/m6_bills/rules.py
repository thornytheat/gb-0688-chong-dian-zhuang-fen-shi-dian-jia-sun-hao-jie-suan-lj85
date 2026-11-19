from decimal import Decimal as D
def compare(rows,tolerance,period_rows=None):
    anomaly_orders=set()
    if period_rows:
        bad_stations={p['station'] for p in period_rows if p['state']!='通过'}
        anomaly_orders={r.get('order') for r in rows if r.get('station') in bad_stations}
    out=[]
    for row in rows:
        period_flag='分时时段异常' if row.get('order') in anomaly_orders else ''
        state='通过' if abs(row['amount']-row['bill'])<=tolerance and row['loss_state']=='通过' else '待复核'
        out.append({**row,'delta':row['amount']-row['bill'],'period_flag':period_flag,'state':state})
    return out
