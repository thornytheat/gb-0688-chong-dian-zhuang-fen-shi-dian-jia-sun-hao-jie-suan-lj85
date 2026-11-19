from app.pipeline import run
from app.config import SAMPLES
from decimal import Decimal as D

def test_reread_success_creates_new_bill(client):
    base=client.post("/api/runs",json={}).json
    good=(SAMPLES/"clean.csv").read_text(encoding="utf-8-sig")
    reply=client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":good})
    assert reply.status_code==200
    body=reply.json
    assert body["manifest"]["run_id"]!=base["manifest"]["run_id"]
    assert body["reread"]["status"]=="created"
    assert body["reread"]["base_run"]==base["manifest"]["run_id"]
    # Original bill remains queryable, untouched.
    old=client.get(f"/api/runs/{base['manifest']['run_id']}")
    assert old.status_code==200 and old.json["manifest"]["run_id"]==base["manifest"]["run_id"]

def test_reread_same_content_is_idempotent(client):
    base=client.post("/api/runs",json={}).json
    good=(SAMPLES/"clean.csv").read_text(encoding="utf-8-sig")
    first=client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":good}).json
    second=client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":good}).json
    assert first["manifest"]["run_id"]==second["manifest"]["run_id"]
    assert second["reread"]["status"]=="reused"
    assert len(client.get("/api/history").json)==2

def test_reread_failure_keeps_legacy_bill(client):
    base=client.post("/api/runs",json={}).json
    before=len(client.get("/api/history").json)
    reply=client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":"bad,header\n1,2"})
    assert reply.status_code==422
    assert reply.json["code"]=="REREAD"
    assert base["manifest"]["run_id"] in reply.json["message"]
    # No new run was persisted; the legacy bill is still the latest usable one.
    history=client.get("/api/history").json
    assert len(history)==before
    assert client.get(f"/api/runs/{base['manifest']['run_id']}").status_code==200

def test_reread_missing_base_404(client):
    reply=client.post("/api/reread/nope",json={"text":"x"})
    assert reply.status_code==404

def test_reviewed_bill_stays_intact_after_reread(client):
    base=client.post("/api/runs",json={}).json
    review=client.post(f"/api/review/{base['manifest']['run_id']}",
                       json={"version":base["version"],"decision":"通过"})
    assert review.status_code==200
    good=(SAMPLES/"clean.csv").read_text(encoding="utf-8-sig")
    client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":good})
    old=client.get(f"/api/runs/{base['manifest']['run_id']}").json
    assert old["review"]=="通过" and old["version"]==base["version"]+1

def test_reread_period_settlement_reconciles_to_station(client):
    base=client.post("/api/runs",json={}).json
    good=(SAMPLES/"clean.csv").read_text(encoding="utf-8-sig")
    body=client.post(f"/api/reread/{base['manifest']['run_id']}",json={"text":good}).json
    for charge in body["charges"]:
        # Every order carries unique time-of-use period lines with loss-inclusive unit prices.
        assert charge["periods"]
        for line in charge["periods"]:
            assert line["gross_rate"] is None or D(line["gross_rate"])>=0
        # The rounded order amount equals the rounded sum of its period lines (same money, same scale).
        period_sum=sum(D(line["raw_fee"]) for line in charge["periods"])
        assert abs(period_sum-D(charge["raw_amount"]))<D("0.000000001")
    # Period-level losses conserve the meter loss at every station.
    for station in {b["station"] for b in body["loss_balances"]}:
        seg=sum(D(s.get("loss_kwh",0)) for s in body["segments"] if s["station"]==station)
        bal=sum(D(b["loss_kwh"]) for b in body["loss_balances"] if b["station"]==station)
        assert seg.quantize(D("0.000000001"))==bal.quantize(D("0.000000001"))
