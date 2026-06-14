"""
分析Shopify商品数据
"""
import json
from pathlib import Path
from collections import Counter
from datetime import datetime

def main():
    # 读取商品索引
    products_file = Path('data/global/products_index.json')
    if not products_file.exists():
        print("未找到商品数据文件")
        return

    with open(products_file, 'r', encoding='utf-8') as f:
        products = json.load(f)

    print("=" * 50)
    print("现有商品数据统计")
    print("=" * 50)
    print(f"商品总数: {len(products)}")
    print()

    # 统计商品类型
    product_types = Counter()
    lifecycle_stages = Counter()
    target_markets = Counter()
    compliance_statuses = Counter()

    for pid, product in products.items():
        product_types[product.get('product_type', '未分类')] += 1
        lifecycle_stages[product.get('lifecycle_stage', 'unknown')] += 1
        status = product.get('compliance_status', 'unknown')
        compliance_statuses[status] += 1

        for market in product.get('target_markets', []):
            target_markets[market] += 1

    print("商品类型分布:")
    for ptype, count in product_types.most_common(10):
        print(f"  {ptype}: {count}")

    print()
    print("生命周期阶段:")
    for stage, count in lifecycle_stages.most_common():
        print(f"  {stage}: {count}")

    print()
    print("目标市场分布:")
    for market, count in target_markets.most_common(10):
        print(f"  {market}: {count}")

    print()
    print("合规状态:")
    for status, count in compliance_statuses.most_common():
        print(f"  {status}: {count}")

    print()
    print("前20个商品示例:")
    print("=" * 50)

    for i, (pid, product) in enumerate(list(products.items())[:20], 1):
        name = product.get('name', '未知商品')
        ptype = product.get('product_type', '未分类')
        stage = product.get('lifecycle_stage', 'unknown')
        markets = ', '.join(product.get('target_markets', []))
        status = product.get('compliance_status', 'unknown')
        updated = product.get('updated_at', 'unknown')

        print(f"{i}. {name}")
        print(f"   类型: {ptype} | 阶段: {stage} | 状态: {status}")
        print(f"   市场: {markets if markets else '无'}")
        print(f"   更新时间: {updated}")
        print(f"   ID: {pid}")
        print()

    # 保存报告到文件
    report_file = Path('data/shopify/products_summary_report.txt')
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("Shopify商品数据分析报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"商品总数: {len(products)}\n\n")

        f.write("商品类型分布:\n")
        for ptype, count in product_types.most_common():
            f.write(f"  {ptype}: {count}\n")

        f.write("\n生命周期阶段:\n")
        for stage, count in lifecycle_stages.most_common():
            f.write(f"  {stage}: {count}\n")

        f.write("\n目标市场分布:\n")
        for market, count in target_markets.most_common():
            f.write(f"  {market}: {count}\n")

        f.write("\n合规状态:\n")
        for status, count in compliance_statuses.most_common():
            f.write(f"  {status}: {count}\n")

    print(f"详细报告已保存到: {report_file}")

if __name__ == "__main__":
    main()