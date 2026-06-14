import json, urllib.request
data = json.load(open("tmp_product.json", "r"))
req = urllib.request.Request("http://localhost:8000/api/v1/products", data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(resp.read().decode("utf-8"))
except Exception as e:
    print(f"ERROR: {e}")
