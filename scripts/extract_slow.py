"""Extract slow request info from logs for CP3 incident analysis."""
import json
import pathlib

log_path = pathlib.Path("data/logs.jsonl")
records = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]

slow = [r for r in records if r.get("latency_ms", 0) > 2000]
print(f"=== Slow requests (>2000ms): {len(slow)} found ===")
for r in slow[:5]:
    cid = r.get("correlation_id", "")
    lat = r.get("latency_ms", "")
    evt = r.get("event", "")
    ts  = r.get("ts", "")
    print(f"  corr={cid}  latency={lat}ms  event={evt}  ts={ts}")

print("\n=== All correlation IDs (first 8): ===")
corr_ids = list(set(r.get("correlation_id", "") for r in records if r.get("correlation_id")))
for c in corr_ids[:8]:
    print(f"  {c}")

print("\n=== Sample log line (response_sent): ===")
for r in records:
    if r.get("event") == "response_sent":
        print(json.dumps(r, ensure_ascii=False, indent=2))
        break
