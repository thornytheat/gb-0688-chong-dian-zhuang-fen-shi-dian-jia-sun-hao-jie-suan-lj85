from .rules import allocate
def execute(ctx):
    orders,balances,period_rows=allocate(ctx['records'],ctx.get('segments'),ctx.get('tariffs'))
    ctx['orders']=orders;ctx['loss_balances']=balances;ctx['period_rows']=period_rows
    ctx['stages'].append({'title':'站内损耗','rows':balances,'metrics':{'站点':len(balances),'损耗 kWh':str(sum((r['loss_kwh'] for r in balances),0)),'异常站':sum(r['state']!='通过' for r in balances),'时段依据':len(period_rows),'时段异常':sum(r['period_anomaly'] for r in balances)}});return ctx
