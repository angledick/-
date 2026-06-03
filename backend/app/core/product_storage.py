"""
产品级隔离存储 (ProductStorage) — 每个产品独立的存储空间。

职责：
  1. 产品CRUD: 创建/读取/更新/删除产品信息
  2. 产品级隔离: 每个产品独立的 events/metrics/memory/knowledge 目录
  3. 产品索引: 全局产品列表和搜索
  4. Shopify导入: 从Shopify产品信息创建产品记录

存储结构:
  data/products/{product_id}/
  ├── product.json         # 产品信息
  ├── events/              # 产品级事件链
  │   └── chain.json
  ├── metrics/             # 产品级指标
  │   └── metrics.json
  ├── memory/              # 产品级记忆（SQLite）
  │   └── memory.db
  └── knowledge/           # 产品级知识
      └── docs.json

全局索引:
  data/global/products_index.json  # 所有产品的索引
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from app.config import settings
from app.models.schemas import (
    ProductInfo, ProductCreateRequest, ProductUpdateRequest,
    ProductLifecycleStage, ProductLifecycleUpdate
)

# ── 存储目录 ──
DATA_DIR = Path(settings.data_dir)
PRODUCTS_DIR = DATA_DIR / "products"
GLOBAL_DIR = DATA_DIR / "global"
INDEX_FILE = GLOBAL_DIR / "products_index.json"


class ProductStorage:
    """产品级隔离存储

    用法:
        storage = ProductStorage()

        # 创建产品
        product = await storage.create_product(ProductCreateRequest(
            name="LED灯带",
            product_type="电子产品",
            target_markets=["德国", "法国"],
            hs_code="9405.40"
        ))

        # 获取产品
        product = storage.get_product("p_led_de_001")

        # 更新产品
        await storage.update_product("p_led_de_001", ProductUpdateRequest(name="LED灯带Pro"))

        # 列出所有产品
        products = storage.list_products()

        # 删除产品（归档）
        await storage.archive_product("p_led_de_001")
    """

    def __init__(self):
        PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
        GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        self._index_cache: Optional[Dict[str, Dict]] = None

    @staticmethod
    def _infer_business_stage(lifecycle_stage: ProductLifecycleStage) -> str:
        """根据产品生命周期阶段推断所属业务阶段"""
        mapping = {
            ProductLifecycleStage.CONCEPT: "阶段2",
            ProductLifecycleStage.DESIGN: "阶段2",
            ProductLifecycleStage.SOURCING: "阶段3",
            ProductLifecycleStage.READY: "阶段4",
            ProductLifecycleStage.ACTIVE: "阶段5",
            ProductLifecycleStage.FULFILLING: "阶段7",
            ProductLifecycleStage.AFTERSALE: "阶段9",
            ProductLifecycleStage.END: "阶段10",
        }
        return mapping.get(lifecycle_stage, "阶段2")

    # ── 产品CRUD ──────────────────────────────────

    async def create_product(self, request: ProductCreateRequest, product_id: str = None) -> ProductInfo:
        """创建产品并初始化隔离存储目录"""
        pid = product_id or f"p_{request.name[:4]}_{uuid.uuid4().hex[:8]}"
        product_dir = PRODUCTS_DIR / pid

        if product_dir.exists():
            raise ValueError(f"产品 {pid} 已存在")

        product = ProductInfo(
            id=pid,
            name=request.name,
            product_type=request.product_type,
            target_markets=request.target_markets,
            hs_code=request.hs_code,
            vendor=request.vendor,
            tags=request.tags,
            lifecycle_stage=ProductLifecycleStage.CONCEPT,
            business_stage=self._infer_business_stage(ProductLifecycleStage.CONCEPT),
        )

        # 创建隔离目录结构
        for subdir in ["events", "metrics", "memory", "knowledge"]:
            (product_dir / subdir).mkdir(parents=True, exist_ok=True)

        # 写入产品信息
        self._write_product(product_dir, product)

        # 更新全局索引
        self._add_to_index(product)

        return product

    def get_product(self, product_id: str) -> Optional[ProductInfo]:
        """获取产品信息"""
        product_dir = PRODUCTS_DIR / product_id
        product_file = product_dir / "product.json"

        if not product_file.exists():
            return None

        try:
            data = json.loads(product_file.read_text(encoding="utf-8"))
            return ProductInfo(**data)
        except Exception:
            return None

    async def update_product(self, product_id: str, request: ProductUpdateRequest) -> Optional[ProductInfo]:
        """更新产品信息"""
        product = self.get_product(product_id)
        if not product:
            return None

        # 应用更新
        update_data = request.model_dump(exclude_none=True)
        for key, value in update_data.items():
            if hasattr(product, key):
                setattr(product, key, value)

        product.updated_at = datetime.now(timezone.utc).isoformat()

        # 写入
        product_dir = PRODUCTS_DIR / product_id
        self._write_product(product_dir, product)
        self._update_index(product)

        return product

    async def update_lifecycle_stage(
        self, product_id: str, update: ProductLifecycleUpdate
    ) -> Optional[ProductInfo]:
        """更新产品生命周期阶段（含状态机校验）"""
        product = self.get_product(product_id)
        if not product:
            return None

        # 状态机校验
        if not self._validate_transition(product.lifecycle_stage, update.lifecycle_stage):
            raise ValueError(
                f"不允许从 {product.lifecycle_stage.value} 转换到 {update.lifecycle_stage.value}"
            )

        old_stage = product.lifecycle_stage
        product.lifecycle_stage = update.lifecycle_stage
        product.business_stage = self._infer_business_stage(update.lifecycle_stage)
        product.updated_at = datetime.now(timezone.utc).isoformat()

        # 写入
        product_dir = PRODUCTS_DIR / product_id
        self._write_product(product_dir, product)
        self._update_index(product)

        return product

    async def delete_product(self, product_id: str) -> bool:
        """删除产品（物理删除）"""
        product_dir = PRODUCTS_DIR / product_id
        if not product_dir.exists():
            return False

        import shutil
        shutil.rmtree(product_dir)
        self._remove_from_index(product_id)
        return True

    async def archive_product(self, product_id: str) -> bool:
        """归档产品（移动到_archive目录）"""
        product_dir = PRODUCTS_DIR / product_id
        if not product_dir.exists():
            return False

        archive_dir = PRODUCTS_DIR / "_archive"
        archive_dir.mkdir(exist_ok=True)

        import shutil
        dest = archive_dir / product_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(product_dir), str(dest))

        self._remove_from_index(product_id)
        return True

    # ── 产品查询 ──────────────────────────────────

    def list_products(
        self,
        lifecycle_stage: Optional[ProductLifecycleStage] = None,
        product_type: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProductInfo]:
        """列出产品（支持过滤和分页）"""
        index = self._load_index()
        products = []

        for pid, meta in index.items():
            if lifecycle_stage and meta.get("lifecycle_stage") != lifecycle_stage.value:
                continue
            if product_type and meta.get("product_type") != product_type:
                continue
            if market and market not in meta.get("target_markets", []):
                continue

            product = self.get_product(pid)
            if product:
                products.append(product)

        return products[offset:offset + limit]

    def count_products(self, lifecycle_stage: Optional[ProductLifecycleStage] = None) -> int:
        """统计产品数量"""
        if lifecycle_stage:
            index = self._load_index()
            return sum(
                1 for meta in index.values()
                if meta.get("lifecycle_stage") == lifecycle_stage.value
            )
        return len(self._load_index())

    def find_by_shopify_id(self, shopify_id: int) -> Optional[ProductInfo]:
        """通过Shopify产品ID查找本地产品"""
        index = self._load_index()
        for pid in index:
            product = self.get_product(pid)
            if product and product.metadata.get("shopify_id") == shopify_id:
                return product
        return None

    def get_product_dir(self, product_id: str) -> Path:
        """获取产品存储目录路径"""
        return PRODUCTS_DIR / product_id

    def get_all_product_ids(self) -> List[str]:
        """获取所有产品ID"""
        return list(self._load_index().keys())

    # ── Shopify导入 ──────────────────────────────────

    async def import_from_shopify(
        self, shopify_product: Dict[str, Any], target_markets: List[str]
    ) -> ProductInfo:
        """从Shopify产品信息创建产品记录"""
        title = shopify_product.get("title", "Unknown")
        product_type = shopify_product.get("product_type", "")
        vendor = shopify_product.get("vendor", "")
        tags = [t.strip() for t in shopify_product.get("tags", "").split(",") if t.strip()]
        handle = shopify_product.get("handle", "")

        request = ProductCreateRequest(
            name=title,
            product_type=product_type,
            target_markets=target_markets,
            vendor=vendor,
            tags=tags,
        )

        product_id = f"p_{handle[:8] if handle else uuid.uuid4().hex[:8]}"
        product = await self.create_product(request, product_id=product_id)

        # 保存Shopify原始数据到产品metadata
        product.metadata = {
            "shopify_id": shopify_product.get("id"),
            "shopify_handle": handle,
            "shopify_variants": shopify_product.get("variants", []),
            "body_html": shopify_product.get("body_html", ""),
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

        product_dir = PRODUCTS_DIR / product_id
        self._write_product(product_dir, product)

        return product

    # ── 内部方法 ──────────────────────────────────

    # 状态机合法转换表
    VALID_TRANSITIONS = {
        ProductLifecycleStage.CONCEPT: [ProductLifecycleStage.DESIGN, ProductLifecycleStage.SOURCING],
        ProductLifecycleStage.DESIGN: [ProductLifecycleStage.SOURCING, ProductLifecycleStage.READY],
        ProductLifecycleStage.SOURCING: [ProductLifecycleStage.READY, ProductLifecycleStage.DESIGN],
        ProductLifecycleStage.READY: [ProductLifecycleStage.ACTIVE, ProductLifecycleStage.SOURCING],
        ProductLifecycleStage.ACTIVE: [ProductLifecycleStage.FULFILLING, ProductLifecycleStage.END],
        ProductLifecycleStage.FULFILLING: [ProductLifecycleStage.AFTERSALE, ProductLifecycleStage.ACTIVE, ProductLifecycleStage.END],
        ProductLifecycleStage.AFTERSALE: [ProductLifecycleStage.END, ProductLifecycleStage.ACTIVE],
        ProductLifecycleStage.END: [ProductLifecycleStage.CONCEPT],  # 重新启用
    }

    @classmethod
    def _validate_transition(cls, from_stage: ProductLifecycleStage, to_stage: ProductLifecycleStage) -> bool:
        """校验状态机转换是否合法"""
        if from_stage == to_stage:
            return True
        allowed = cls.VALID_TRANSITIONS.get(from_stage, [])
        return to_stage in allowed

    def _write_product(self, product_dir: Path, product: ProductInfo):
        """写入产品信息到JSON"""
        product_file = product_dir / "product.json"
        product_file.write_text(
            json.dumps(product.model_dump(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _load_index(self) -> Dict[str, Dict]:
        """加载全局产品索引"""
        if self._index_cache is not None:
            return self._index_cache

        if not INDEX_FILE.exists():
            self._index_cache = {}
            return self._index_cache

        try:
            self._index_cache = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            self._index_cache = {}
        return self._index_cache

    def _save_index(self):
        """保存全局产品索引"""
        if self._index_cache is None:
            return
        INDEX_FILE.write_text(
            json.dumps(self._index_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _add_to_index(self, product: ProductInfo):
        """添加产品到全局索引"""
        index = self._load_index()
        index[product.id] = {
            "name": product.name,
            "product_type": product.product_type,
            "lifecycle_stage": product.lifecycle_stage.value,
            "target_markets": product.target_markets,
            "compliance_status": product.compliance_status,
            "risk_level": product.risk_level,
            "updated_at": product.updated_at,
        }
        self._index_cache = index
        self._save_index()

    def _update_index(self, product: ProductInfo):
        """更新全局索引中的产品"""
        self._add_to_index(product)

    def _remove_from_index(self, product_id: str):
        """从全局索引移除产品"""
        index = self._load_index()
        if product_id in index:
            del index[product_id]
        self._save_index()


# ── 全局单例 ──────────────────────────────────

_product_storage: Optional[ProductStorage] = None


def get_product_storage() -> ProductStorage:
    """获取产品存储单例"""
    global _product_storage
    if _product_storage is None:
        _product_storage = ProductStorage()
    return _product_storage
