"""Load and chunk compliance regulation documents.

数据流转:
  L0 data/regulations/{market}/*.md  →  分块  →  写入 L1 ChromaDB
  每份文件含 YAML frontmatter（regulation_id / name / source_url / tags 等）
  分块时将 frontmatter 元数据附加到每个 chunk，供 RAG citation 使用。

读取者: init_knowledge.py / scheduler
"""

import re
from pathlib import Path
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import settings

# ── 分块器 ────────────────────────────────────────────────────────────────────
_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    separators=["\n## ", "\n### ", "\n#### ", "\n---\n", "\n\n", "\n", " "],
)


# ── YAML frontmatter 解析 ─────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """提取 YAML frontmatter 和正文。

    仅解析简单 key: "value" 格式，不引入 PyYAML 以避免依赖冲突。

    Returns:
        (meta_dict, body_text)
    """
    meta: dict = {}
    body = text

    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return meta, body

    fm_block = m.group(1)
    body = text[m.end():]

    for line in fm_block.splitlines():
        kv = re.match(r'^(\w+):\s*"?(.*?)"?\s*$', line.strip())
        if kv:
            meta[kv.group(1)] = kv.group(2)

    return meta, body


# ── 目录扫描加载（主接口）────────────────────────────────────────────────────

def load_regulations_dir(market: Optional[str] = None) -> list[dict]:
    """扫描 data/regulations/ 目录，加载所有法规文件并分块。

    Args:
        market: 市场代码（eu/de/us/jp/kr），None 表示加载全部

    Returns:
        list of {
            "regulation_id": str,
            "market": str,
            "chunks": list[str],
            "metadatas": list[dict],   # 与 chunks 等长，每块含完整元数据
        }
    """
    base = Path(settings.data_dir) / "regulations"
    if not base.exists():
        return []

    # 确定扫描范围
    if market:
        dirs = [base / market] if (base / market).is_dir() else []
    else:
        dirs = [d for d in base.iterdir() if d.is_dir()]

    results = []
    for market_dir in sorted(dirs):
        mkt = market_dir.name
        for md_file in sorted(market_dir.glob("*.md")):
            raw = md_file.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(raw)

            reg_id   = fm.get("regulation_id") or md_file.stem
            reg_name = fm.get("name", reg_id)
            src_url  = fm.get("source_url", "")
            eff_date = fm.get("effective_date", "")
            tags     = fm.get("tags", "")

            chunks = _SPLITTER.split_text(body)
            if not chunks:
                continue

            metadatas = [
                {
                    "market":           mkt,
                    "regulation_id":    reg_id,
                    "regulation_name":  reg_name,
                    "source_url":       src_url,
                    "effective_date":   eff_date,
                    "tags":             tags,
                    "chunk_index":      i,
                }
                for i in range(len(chunks))
            ]

            results.append({
                "regulation_id": reg_id,
                "market":        mkt,
                "chunks":        chunks,
                "metadatas":     metadatas,
            })

    return results


# ── 向后兼容接口 ──────────────────────────────────────────────────────────────

def load_regulations(file_path: Optional[str] = None, market: str = "eu") -> list[str]:
    """向后兼容接口——加载单个文件并返回文本块列表。

    优先级:
      1. file_path 指定路径
      2. data/raw/regulations/{market}/_all.md
      3. data/regulations.md（旧路径）
    """
    if file_path is not None:
        path = Path(file_path)
    else:
        new_path = Path(settings.data_dir) / "raw" / "regulations" / market / "_all.md"
        path = new_path if new_path.exists() else Path(settings.data_dir) / "regulations.md"

    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    return _SPLITTER.split_text(text)
