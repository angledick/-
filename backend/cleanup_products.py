"""清理所有测试产品数据"""
import json
import shutil
from pathlib import Path

products_dir = Path("data/products")
index_file = Path("data/global/products_index.json")

# 读取索引
if index_file.exists():
    index = json.loads(index_file.read_text(encoding="utf-8"))
    print(f"索引中有 {len(index)} 个产品")
    for pid in list(index.keys())[:10]:
        print(f"  {pid}: {index[pid].get('name', '?')}")
    if len(index) > 10:
        print(f"  ... 共 {len(index)} 个")
else:
    print("索引文件不存在")
    index = {}

# 清理所有产品目录
if products_dir.exists():
    dirs = [d for d in products_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
    print(f"产品目录中有 {len(dirs)} 个产品文件夹")
    for d in dirs:
        shutil.rmtree(d)
        print(f"  已删除: {d.name}")

# 清空索引
index_file.write_text("{}", encoding="utf-8")
print(f"\n索引已清空，删除了 {len(index)} 个产品")

