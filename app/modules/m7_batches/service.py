from .rules import summary
def execute(ctx):
    ctx['audit']=summary(ctx['records'],ctx['quarantine'],ctx['input_count'],ctx['segments'],ctx['loss_balances'],ctx['charges'],ctx.get('period_rows'),ctx.get('orders'))
    ctx['stages'].append({'title':'结算清单','rows':[ctx['audit']],'metrics':{'采信':len(ctx['records']),'隔离':len(ctx['quarantine']),'异常站':ctx['audit']['blocked_stations'],'时段异常':ctx['audit']['period_anomaly']}});return ctx
