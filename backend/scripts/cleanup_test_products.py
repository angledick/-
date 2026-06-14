"""清理系统内测试商品数据（E2E测试/LED灯测试等），保留 shopify_* 真实商品"""
import json
import shutil
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
products_dir = backend_dir / "data" / "products"
index_file = backend_dir / "data" / "global" / "products_index.json"

# Load index
with open(index_file, "r", encoding="utf-8") as f:
    index = json.load(f)

print("Before cleanup:")
print(f"  Index entries: {len(index)}")
print(f"  Product dirs: {len([d for d in products_dir.iterdir() if d.is_dir()])}")

# Identify test data (keep only shopify_* products)
test_pids_in_index = [pid for pid in index if not pid.startswith("shopify_")]
print(f"  Test entries in index: {len(test_pids_in_index)}")

# Remove test product directories
test_dirs = [
    d for d in products_dir.iterdir() if d.is_dir() and not d.name.startswith("shopify_")
]
print(f"  Test product dirs: {len(test_dirs)}")

for d in test_dirs:
    shutil.rmtree(d)

# Clean index - keep only shopify_* entries
clean_index = {
    pid: meta for pid, meta in index.items() if pid.startswith("shopify_")
}
print(f"  Remaining index entries: {len(clean_index)}")

# Save cleaned index
with open(index_file, "w", encoding="utf-8") as f:
    json.dump(clean_index, f, ensure_ascii=False, indent=2)

# Verify remaining directories
remaining = [d.name for d in products_dir.iterdir() if d.is_dir()]
print("\nAfter cleanup:")
print(f"  Remaining dirs: {remaining}")
print(f"  Index entries: {len(clean_index)}")
for pid, meta in clean_index.items():
    name = meta.get("name", "?")
    stage = meta.get("lifecycle_stage", "?")
    print(f"    {pid}: {name} ({stage})")
