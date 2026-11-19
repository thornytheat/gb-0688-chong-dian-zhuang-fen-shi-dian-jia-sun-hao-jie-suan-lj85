import hashlib, json
from datetime import datetime, timezone
from app.config import RULE_VERSION
def make(raw,params,base_run=None):
    digest=hashlib.sha256(raw).hexdigest()
    scope=digest+json.dumps(params,sort_keys=True,ensure_ascii=False)+RULE_VERSION
    if base_run:scope+="|reread-of:"+base_run
    key=hashlib.sha256(scope.encode()).hexdigest()
    return {"run_id":key[:20],"sha256":digest,"rules":RULE_VERSION,"params":params,
            "created":datetime.now(timezone.utc).isoformat(),"bytes":len(raw),
            **({"base_run":base_run} if base_run else {})}
