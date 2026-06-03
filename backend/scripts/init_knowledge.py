#!/usr/bin/env python3
"""init_knowledge.py — 初始化合规知识库

数据流:
  data/regulations/{market}/*.md  →  分块  →  sentence-transformer 向量化
  →  写入 L1 ChromaDB (按 market 分 collection)

用法:
    cd backend
    python scripts/init_knowledge.py                      # 默认 EU
    python scripts/init_knowledge.py --all-markets        # 所有市场
    python scripts/init_knowledge.py --market eu de       # 指定市场
    python scripts/init_knowledge.py --fetch              # 先下载文档再初始化
    python scripts/init_knowledge.py --fetch --all-markets --reset
    python scripts/init_knowledge.py --reset              # 清空后重建
    python scripts/init_knowledge.py --dry-run            # 预览分块
"""

import argparse
import sys
sys.path.insert(0, ".")

from app.knowledge.loader import load_regulations_dir
from app.knowledge.store import upsert_documents, clear_collection, get_document_count
from app.knowledge.market_routing import get_all_collections


def _init_market(market: str, reset: bool, dry_run: bool) -> int:
    """初始化单个市场的知识库。返回写入文档数。"""
    print(f"\n{'─'*50}")
    print(f"🌍  市场: {market.upper()}")
    print(f"{'─'*50}")

    docs = load_regulations_dir(market=market)
    if not docs:
        print(f"   ⚠️  data/regulations/{market}/ 无文件，跳过")
        print(f"   提示: 先运行 python scripts/fetch_regulations.py --market {market}")
        return 0

    total_chunks = sum(len(d["chunks"]) for d in docs)
    print(f"📄  加载 {len(docs)} 份法规  →  {total_chunks} 个文本块")

    if dry_run:
        for doc in docs:
            print(f"\n  [{doc['regulation_id']}]  {len(doc['chunks'])} chunks")
            if doc["chunks"]:
                preview = doc["chunks"][0][:200].replace("\n", " ")
                print(f"    首块预览: {preview}...")
        return 0

    if reset:
        print("🧹  清空现有 collection...")
        clear_collection(market=market)

    written = 0
    for doc in docs:
        reg_id = doc["regulation_id"]
        chunks = doc["chunks"]
        metas  = doc["metadatas"]
        print(f"  💾  {reg_id:<30}  {len(chunks):>4} chunks", end="", flush=True)
        upsert_documents(chunks, metas, market=market, regulation_id=reg_id)
        written += len(chunks)
        print("  ✓")

    total_in_db = get_document_count(market=market)
    print(f"\n✅  {market.upper()} 完成 — ChromaDB 现有 {total_in_db} 个文档")
    return written


def main():
    parser = argparse.ArgumentParser(description="避风港 — 初始化合规知识库")
    parser.add_argument(
        "--market", nargs="+", metavar="CODE",
        help="指定市场代码 (eu de us jp kr)，可多选",
    )
    parser.add_argument(
        "--all-markets", action="store_true",
        help="初始化所有市场 (eu, de, us, jp, kr)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="清空现有数据后重建",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览分块，不写入 ChromaDB",
    )
    parser.add_argument(
        "--fetch", action="store_true",
        help="先下载法规文档（fetch_regulations.py），再初始化",
    )
    args = parser.parse_args()

    # 确定目标市场
    if args.all_markets:
        markets = ["eu", "de", "us", "jp", "kr"]
    elif args.market:
        markets = args.market
    else:
        markets = ["eu"]

    # 可选：先下载文档
    if args.fetch:
        print("\n📥  先下载合规文档...")
        from scripts.fetch_regulations import run as fetch_run
        fetch_run(markets=markets if not args.all_markets else None)

    print(f"\n🔧  初始化知识库 — 目标市场: {markets}")
    print(f"    embedding model: paraphrase-multilingual-MiniLM-L12-v2 (本地)")
    print(f"    (首次运行会自动下载模型，约 120MB)\n")

    total_written = 0
    for market in markets:
        total_written += _init_market(market, args.reset, args.dry_run)

    if not args.dry_run:
        grand_total = sum(
            get_document_count(market=m)
            for m in ["eu", "de", "us", "jp", "kr"]
        )
        print(f"\n{'═'*50}")
        print(f"📊  全部完成！本次写入 {total_written} chunks")
        print(f"    ChromaDB 全库总计: {grand_total} 个文档")
        print(f"{'═'*50}\n")


if __name__ == "__main__":
    main()
