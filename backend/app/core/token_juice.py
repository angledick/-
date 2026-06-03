"""
TokenJuice 智能Token压缩层 — 基于OpenHuman TokenJuice设计。

职责：
  1. HTML → Markdown 转换: 去除HTML标签，保留结构化内容
  2. 长URL缩短: 截断过长URL，保留域名
  3. 工具输出去重: 移除重复的工具输出片段
  4. 冗余模板去除: 识别并压缩重复的模板文本
  5. 多字节字符保护: 确保中文/日文等多字节字符不被截断
  6. Shopify响应压缩: 针对Shopify API响应的专用压缩

开源参考:
  - OpenHuman TokenJuice: 智能Token压缩
  - 目标: 压缩率30%-70%，保留关键业务信息

用法:
    juice = TokenJuice()
    result = await juice.compress(html_content, content_type="html")
    print(f"压缩率: {result.ratio:.1%}, 节省: {result.tokens_saved} tokens")
"""

import re
import json
import hashlib
from typing import Optional, Dict, Any, List
from collections import Counter

from app.models.schemas import CompressedData


class TokenJuice:
    """智能Token压缩层

    用法:
        juice = TokenJuice()

        # 通用压缩
        result = await juice.compress(long_text, content_type="text")

        # HTML压缩
        result = await juice.compress(html_content, content_type="html")

        # Shopify API响应压缩
        compressed = await juice.compress_shopify_response(shopify_data)

        # 批量压缩
        results = await juice.compress_batch([text1, text2, text3])

        # 压缩统计
        stats = juice.get_stats()
    """

    def __init__(self):
        self._total_original = 0
        self._total_compressed = 0
        self._compress_count = 0
        # HTML标签白名单（保留结构化信息）
        self._keep_tags = {"b", "strong", "em", "i", "a", "br", "p", "h1", "h2", "h3", "ul", "ol", "li", "table", "tr", "td", "th"}
        # Shopify响应中需移除的字段
        self._shopify_remove_fields = {
            "admin_graphql_api_id", "published_scope", "template_suffix",
            "tags_raw", "metafields_global_title_tag", "metafields_global_description_tag",
            "created_at", "updated_at", "published_at",
        }

    # ── 通用压缩 ──────────────────────────────────

    async def compress(self, data: str, content_type: str = "text") -> CompressedData:
        """压缩数据

        Args:
            data: 待压缩数据
            content_type: 数据类型 text/html/json
        Returns:
            CompressedData 含压缩前后内容和压缩率
        """
        original = data
        original_len = len(original)

        # 1. HTML → Markdown
        if content_type == "html":
            data = self._html_to_markdown(data)

        # 2. JSON精简
        if content_type == "json":
            data = self._compress_json(data)

        # 3. 长URL缩短
        data = self._shorten_urls(data)

        # 4. 工具输出去重
        data = self._remove_duplicates(data)

        # 5. 冗余模板去除
        data = self._remove_templates(data)

        # 6. 空白字符规范化
        data = self._normalize_whitespace(data)

        # 7. 多字节字符保护
        data = self._protect_multibyte(data)

        compressed_len = len(data)
        ratio = compressed_len / original_len if original_len > 0 else 1.0
        tokens_saved = self._estimate_tokens(original) - self._estimate_tokens(data)

        # 更新统计
        self._total_original += original_len
        self._total_compressed += compressed_len
        self._compress_count += 1

        return CompressedData(
            original=original[:200] + "..." if len(original) > 200 else original,
            compressed=data,
            ratio=ratio,
            tokens_saved=max(0, tokens_saved),
        )

    async def compress_batch(self, items: List[str], content_type: str = "text") -> List[CompressedData]:
        """批量压缩"""
        results = []
        for item in items:
            result = await self.compress(item, content_type)
            results.append(result)
        return results

    # ── Shopify专用压缩 ──────────────────────────────

    async def compress_shopify_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """压缩Shopify API响应

        策略:
        1. 移除admin_graphql_api_id等无用字段
        2. 压缩嵌套的variants列表（保留核心字段）
        3. HTML描述转Markdown
        4. 截断过长的tags
        """
        if not isinstance(response, dict):
            return response

        compressed = {}
        for key, value in response.items():
            # 移除无用字段
            if key in self._shopify_remove_fields:
                continue

            # 处理variants列表
            if key == "variants" and isinstance(value, list):
                compressed[key] = [
                    self._compress_variant(v) for v in value[:20]  # 最多保留20个变体
                ]
                continue

            # HTML描述转Markdown
            if key == "body_html" and isinstance(value, str):
                compressed[key] = self._html_to_markdown(value)
                continue

            # 截断过长tags
            if key == "tags" and isinstance(value, str):
                tags = [t.strip() for t in value.split(",") if t.strip()]
                compressed[key] = ", ".join(tags[:30])  # 最多30个标签
                continue

            # 递归处理嵌套dict
            if isinstance(value, dict):
                compressed[key] = await self.compress_shopify_response(value)
                continue

            # 其他字段原样保留
            compressed[key] = value

        return compressed

    def _compress_variant(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """压缩单个Shopify变体"""
        keep_fields = {"id", "title", "price", "sku", "inventory_quantity", "requires_shipping", "weight"}
        return {k: v for k, v in variant.items() if k in keep_fields}

    # ── 压缩策略实现 ──────────────────────────────

    def _html_to_markdown(self, html: str) -> str:
        """HTML → Markdown 转换（轻量级，不依赖外部库）"""
        # 移除script/style标签
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 标题转换
        for i in range(1, 7):
            text = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', rf'\n{"#" * i} \1\n', text, flags=re.IGNORECASE)

        # 加粗/斜体
        text = re.sub(r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**', text, flags=re.IGNORECASE)
        text = re.sub(r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', r'*\1*', text, flags=re.IGNORECASE)

        # 链接转换
        text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)

        # 列表转换
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', text, flags=re.IGNORECASE)

        # 段落和换行
        text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.IGNORECASE | re.DOTALL)

        # 表格简化
        text = re.sub(r'<t[hd][^>]*>(.*?)</t[hd]>', r'| \1 ', text, flags=re.IGNORECASE)
        text = re.sub(r'</tr>', '|\n', text, flags=re.IGNORECASE)

        # 移除所有剩余HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 解码常见HTML实体
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")

        return text.strip()

    def _shorten_urls(self, text: str, max_len: int = 80) -> str:
        """缩短过长URL"""
        def shorten(match):
            url = match.group(0)
            if len(url) <= max_len:
                return url
            # 保留协议和域名
            parts = url.split("/", 3)
            if len(parts) >= 3:
                domain = "/".join(parts[:3])
                return f"{domain}/..."
            return url[:max_len] + "..."

        return re.sub(r'https?://[^\s\)]+', shorten, text)

    def _remove_duplicates(self, text: str) -> str:
        """去除重复段落"""
        lines = text.split("\n")
        seen = set()
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result.append(line)
                continue
            line_hash = hashlib.md5(stripped.encode()).hexdigest()
            if line_hash not in seen:
                seen.add(line_hash)
                result.append(line)
        return "\n".join(result)

    def _remove_templates(self, text: str) -> str:
        """移除重复的模板文本"""
        # 检测重复率超过50%的连续行块
        paragraphs = text.split("\n\n")
        if len(paragraphs) < 3:
            return text

        # 统计段落频率
        para_counts = Counter(p.strip() for p in paragraphs if p.strip())
        result = []
        seen_repeated = set()

        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                result.append(para)
                continue
            if para_counts[stripped] > 2 and stripped in seen_repeated:
                continue  # 跳过重复的模板段落
            if para_counts[stripped] > 2:
                seen_repeated.add(stripped)
            result.append(para)

        return "\n\n".join(result)

    def _normalize_whitespace(self, text: str) -> str:
        """规范化空白字符"""
        # 多个连续空行合并为一个
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 行尾空白去除
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        # 多个空格合并（但保留缩进）
        text = re.sub(r'(?<!\n) {2,}', ' ', text)
        return text.strip()

    def _compress_json(self, json_str: str) -> str:
        """精简JSON数据"""
        try:
            data = json.loads(json_str)
            # 移除null值和空数组/对象
            cleaned = self._clean_json(data)
            return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
        except (json.JSONDecodeError, Exception):
            return json_str

    def _clean_json(self, data: Any, depth: int = 0) -> Any:
        """递归清理JSON"""
        if depth > 10:
            return str(data)[:100]

        if isinstance(data, dict):
            return {
                k: self._clean_json(v, depth + 1)
                for k, v in data.items()
                if v is not None and v != "" and v != [] and v != {}
            }
        elif isinstance(data, list):
            # 截断超长列表
            cleaned = [self._clean_json(item, depth + 1) for item in data[:50]]
            if len(data) > 50:
                cleaned.append(f"... ({len(data) - 50} more items)")
            return cleaned
        elif isinstance(data, str) and len(data) > 500:
            return data[:500] + "..."
        return data

    def _protect_multibyte(self, text: str) -> str:
        """保护多字节字符不被截断"""
        # 确保不在多字节字符中间截断
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            text = text.encode("utf-8", errors="replace").decode("utf-8")
        return text

    # ── 工具方法 ──────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """估算token数（粗略: 英文4字符/token，中文1.5字符/token）"""
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - cn_chars
        return int(cn_chars / 1.5 + other_chars / 4)

    def get_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        total_ratio = (
            self._total_compressed / self._total_original
            if self._total_original > 0 else 1.0
        )
        return {
            "total_original_chars": self._total_original,
            "total_compressed_chars": self._total_compressed,
            "total_saved_chars": self._total_original - self._total_compressed,
            "compression_ratio": total_ratio,
            "compress_count": self._compress_count,
            "avg_saved_per_call": (
                (self._total_original - self._total_compressed) / self._compress_count
                if self._compress_count > 0 else 0
            ),
        }


# ── 全局单例 ──────────────────────────────────

_token_juice: Optional[TokenJuice] = None


def get_token_juice() -> TokenJuice:
    """获取TokenJuice单例"""
    global _token_juice
    if _token_juice is None:
        _token_juice = TokenJuice()
    return _token_juice
