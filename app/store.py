import os,sqlite3,json
from pathlib import Path
from app.errors import DomainError
def connection():
    path=Path(os.environ.get("DATA_DIR","data"));path.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path/"runs.sqlite",timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,review TEXT NOT NULL DEFAULT '待复核')")
    return db
def save(result):
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES(?,?)",(result["manifest"]["run_id"],json.dumps(result,ensure_ascii=False)))
    return fetch(result["manifest"]["run_id"])
def fetch(run_id):
    with connection() as db: row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
    result=json.loads(row["payload"]);result["version"]=row["version"];result["review"]=row["review"]
    return result
def history():
    with connection() as db: rows=db.execute("SELECT id,version,review FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [dict(row) for row in rows]
def review(run_id,version,decision):
    if decision not in ("通过","退回"): raise DomainError("REVIEW","请选择通过或退回")
    if not isinstance(version,int): raise DomainError("STALE","版本必须为整数")
    with connection() as db:
        cur=db.execute("UPDATE runs SET review=?,version=version+1 WHERE id=? AND version=?",(decision,run_id,version))
        if cur.rowcount!=1: raise DomainError("STALE","复核版本已更新",409)
    return fetch(run_id)
def reread(base_id,new_result):
    """补读：仅在新批次可完整计算且与旧批次不同时落账；失败调用方不得写入，旧账原样保留。"""
    new_id=new_result["manifest"]["run_id"]
    with connection() as db:
        row=db.execute("SELECT id,version,review FROM runs WHERE id=?",(base_id,)).fetchone()
        if row is None: raise DomainError("NOT_FOUND","原批次不存在，无法补读",404)
        cur=db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES(?,?)",(new_id,json.dumps(new_result,ensure_ascii=False)))
        created=cur.rowcount==1
    result=fetch(new_id)
    result["reread"]={"base_run":base_id,"status":"created" if created else "reused",
                      "base_review":row["review"],"base_version":row["version"]}
    return result
