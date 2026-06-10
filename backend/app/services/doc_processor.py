"""文档处理器 — PDF 和 URL 内容提取 + 分块。

流程: 原始内容 → 文本提取 → 清洗 → 分块 → 返回 chunks 列表
"""

import io
import logging
import re
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# 分块参数
CHUNK_SIZE    = 600   # 字符数（中文约 400 词，英文约 100 词）
CHUNK_OVERLAP = 80


# ── 文本清洗 ──────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r"\s{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """将长文本按字符数分块，相邻块有重叠以保持上下文连贯。"""
    text = _clean(text)
    if not text:
        return []

    # 优先在段落/句子边界分割
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        if not para.strip():
            continue
        if len(buf) + len(para) <= size:
            buf = (buf + "\n\n" + para).strip()
        else:
            if buf:
                chunks.append(buf)
                # 重叠：取 buf 末尾 overlap 字符作为下一块开头
                buf = buf[-overlap:].strip() + "\n\n" + para
                buf = buf.strip()
            else:
                # 单段就超过 size，强制按字符切
                while len(para) > size:
                    chunks.append(para[:size])
                    para = para[size - overlap:]
                buf = para.strip()

    if buf:
        chunks.append(buf)

    return [c for c in chunks if len(c) >= 30]   # 过滤过短碎片


# ── PDF 提取 ──────────────────────────────────────────────────────────

def extract_pdf(content: bytes) -> str:
    """从 PDF 二进制内容提取全文。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        log.warning("PDF 提取失败: %s", e)
        raise ValueError(f"PDF 解析失败: {e}")


def process_pdf(content: bytes, filename: str, market: str = "custom",
                source_url: str = "") -> list[dict]:
    """PDF → chunks，每个 chunk 附带元数据。"""
    raw = extract_pdf(content)
    chunks = _split_chunks(raw)
    log.info("[doc] PDF '%s' → %d 块", filename, len(chunks))

    return [
        {
            "text":       chunk,
            "doc_type":   "pdf",
            "filename":   filename,
            "source_url": source_url or f"file://{filename}",
            "market":     market,
            "page_hint":  i + 1,
        }
        for i, chunk in enumerate(chunks)
    ]


# ── URL / 网页提取 ────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AstraKnowledgeBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _html_to_text(html: str) -> str:
    """BeautifulSoup 提取正文，去掉脚本/样式/导航。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # 删除无关标签
    for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                               "aside", "advertisement", "iframe"]):
        tag.decompose()

    # 尝试找主体内容
    main = (
        soup.find("article") or
        soup.find("main") or
        soup.find(id=re.compile(r"content|main|body|article", re.I)) or
        soup.find(class_=re.compile(r"content|main|body|article|post", re.I)) or
        soup.body
    )
    return (main or soup).get_text(separator="\n")


def fetch_url(url: str, timeout: int = 20) -> tuple[str, str]:
    """下载 URL，返回 (文本内容, 页面标题)。

    支持普通网页和 PDF URL。
    """
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=timeout,
                       follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"HTTP {e.response.status_code}: {url}")
    except Exception as e:
        raise ValueError(f"请求失败: {e}")

    content_type = r.headers.get("content-type", "")

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        text = extract_pdf(r.content)
        title = url.split("/")[-1]
        return text, title

    if "html" not in content_type and "text" not in content_type:
        raise ValueError(f"不支持的内容类型: {content_type}")

    # 获取标题
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else url

    text = _html_to_text(r.text)
    return text, title


def process_url(url: str, market: str = "custom",
                regulation_name: str = "") -> list[dict]:
    """URL → chunks，每个 chunk 附带元数据。"""
    text, title = fetch_url(url)
    name = regulation_name or title
    chunks = _split_chunks(text)
    log.info("[doc] URL '%s' → %d 块", url, len(chunks))

    return [
        {
            "text":            chunk,
            "doc_type":        "url",
            "filename":        title,
            "source_url":      url,
            "regulation_name": name,
            "market":          market,
            "page_hint":       i + 1,
        }
        for i, chunk in enumerate(chunks)
    ]
