import json, os, time
p='tmp/kalshi_ref_arb/last_cycle_status.json'
if not os.path.exists(p):
    exit(2)
with open(p,'r') as f:
    d=json.load(f)
ts=int(d.get('ts_unix') or 0)
print(int(time.time())-ts)
exit(0 if (int(time.time())-ts)<=600 else 3)
