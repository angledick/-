"""
数据迁移脚本 — 将旧数据文件迁移到 L0-L5 分层存储结构。

执行:
    python scripts/migrate_storage.py

迁移内容:
    1. data/hs_codes.json       → data/raw/hs_codes/_all.json
    2. data/vat_rates.json      → data/raw/vat_rates/_all.json
    3. data/regulations.md      → data/raw/regulations/eu/_all.md
    4. data/chains/actions/*    → data/event_chain/system_events/ (通过 EventStore.migrate_from_old_dirs)
    5. data/chains/events/*     → data/event_chain/system_events/
    6. rule_engine.py _cert_map → data/raw/certifications/cert_matrix.json（已提取）
"""

import json
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.storage.event_store import EventStore


def migrate_raw_data():
    """迁移原始数据文件到 L0 data/raw/ 目录。"""
    old_data = Path(settings.data_dir)
    raw_base = old_data / "raw"

    migrations = [
        ("hs_codes.json", "hs_codes/_all.json"),
        ("vat_rates.json", "vat_rates/_all.json"),
    ]

    stats = []
    for src_name, dest_rel in migrations:
        src = old_data / src_name
        dest = raw_base / dest_rel
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            stats.append(f"  ✅ {src_name} → {dest_rel}")
        else:
            stats.append(f"  ⚠️ {src_name} 不存在，跳过")

    # 迁移 regulations.md
    reg_src = old_data / "regulations.md"
    reg_dest = raw_base / "regulations" / "eu" / "_all.md"
    if reg_src.exists():
        reg_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reg_src, reg_dest)
        stats.append(f"  ✅ regulations.md → regulations/eu/_all.md")
    else:
        stats.append(f"  ⚠️ regulations.md 不存在，跳过")

    return stats


def migrate_event_chains():
    """迁移事件链和操作链到 L5。"""
    store = EventStore()
    stats = store.migrate_from_old_dirs()
    return [
        f"  ✅ 操作链迁移: {stats['actions_migrated']} 条",
        f"  ✅ 事件链迁移: {stats['events_migrated']} 条",
    ]


def run():
    """执行全部数据迁移。"""
    print("=" * 50)
    print("开始数据迁移 — 旧结构 → L0-L5 分层存储")
    print("=" * 50)

    print("\n📁 L0 原始数据迁移:")
    for s in migrate_raw_data():
        print(s)

    print("\n📁 L5 事件链迁移:")
    for s in migrate_event_chains():
        print(s)

    print("\n📁 认证矩阵:")
    cert_path = Path(settings.data_dir) / "raw" / "certifications" / "cert_matrix.json"
    if cert_path.exists():
        print(f"  ✅ cert_matrix.json 已就绪")
    else:
        print(f"  ⚠️ cert_matrix.json 不存在（需手动创建）")

    print("\n" + "=" * 50)
    print("迁移完成。旧文件仍在原位，确认无问题后可手动删除。")
    print("=" * 50)


if __name__ == "__main__":
    run()
