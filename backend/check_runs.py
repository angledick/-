import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/risk-intel/runs', method='GET')
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())
    runs = data if isinstance(data, list) else [data]
    print(f'Runs: {len(runs)}')
    for r in runs[-5:]:
        rid = r.get('id', '')[:12]
        kw = r.get('keyword', '')
        st = r.get('status', '')
        found = r.get('items_found', '')
        new = r.get('items_new', '')
        err = str(r.get('error_msg') or '')[:100]
        print(f'  id={rid} kw={kw} status={st} found={found} new={new} err={err}')
