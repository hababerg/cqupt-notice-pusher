"""
独立爬虫测试脚本
=================
不依赖 MCP 环境，直接测试爬取 + 解析 + 去重的完整流程。

使用方法：
    python tests/test_crawler.py            # 爬取当天通知，不标记已推送
    python tests/test_crawler.py --all      # 爬取页面上所有通知（不按日期过滤）
    python tests/test_crawler.py --days 3   # 爬取最近 3 天的通知
    python tests/test_crawler.py --no-head  # 有头模式（可看到浏览器操作）
"""

import sys
import os
import json
from datetime import datetime

# 确保能导入上一级目录的 mcp_server.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server import (
    load_config,
    fetch_page_html,
    parse_notices,
    filter_by_date,
    filter_unpushed,
    load_pushed_records,
    mark_as_pushed,
    DEFAULT_CONFIG,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CQUPT 通知爬虫独立测试")
    parser.add_argument("--all", action="store_true",
                        help="不按日期过滤，显示页面上所有通知")
    parser.add_argument("--days", type=int, default=1,
                        help="抓取最近 N 天的通知（默认 1）")
    parser.add_argument("--no-head", action="store_true",
                        help="有头模式运行 Chrome（可见浏览器）")
    parser.add_argument("--mark", action="store_true",
                        help="将本次结果标记为已推送")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["headless"] = not args.no_head

    print("=" * 60)
    print("  CQUPT 教务处通知爬虫 - 独立测试")
    print("=" * 60)
    print(f"目标 URL : {config['target_url']}")
    print(f"无头模式 : {config['headless']}")
    print(f"日期范围 : {'全部' if args.all else f'最近 {args.days} 天'}")
    print("=" * 60)

    # 1. 爬取
    print("\n[1/4] 正在爬取页面...")
    html = fetch_page_html(config["target_url"], config)
    if not html:
        print("❌ 爬取失败！请检查网络或 Chrome 是否安装。")
        sys.exit(1)
    print(f"✅ 爬取成功，HTML 长度: {len(html)}")

    # 2. 解析
    print("\n[2/4] 正在解析通知列表...")
    notices = parse_notices(html)
    if not notices:
        print("❌ 未解析到任何通知！页面结构可能已变化。")
        sys.exit(1)
    print(f"✅ 解析到 {len(notices)} 条通知")

    # 3. 日期过滤
    print(f"\n[3/4] 日期过滤（{'全部' if args.all else f'最近 {args.days} 天'}）...")
    if args.all:
        recent = notices
    else:
        recent = filter_by_date(notices, args.days)
    print(f"✅ 过滤后剩余 {len(recent)} 条通知")

    # 4. 去重
    print("\n[4/4] 去重检查...")
    record_file = config["record_file"]
    records = load_pushed_records(record_file)
    print(f"   已推送记录: {len(records)} 条")
    new_notices = filter_unpushed(recent, record_file)
    print(f"✅ 去重后剩余 {len(new_notices)} 条新通知")

    # 输出结果
    print("\n" + "=" * 60)
    print("  爬取结果")
    print("=" * 60)

    if not recent:
        print("（指定日期范围内没有通知）")
    else:
        for i, n in enumerate(recent, 1):
            status = "🆕 新" if n["url"] not in records else "📌 已推送"
            print(f"\n{i}. [{n['date']}] {status}")
            print(f"   标题: {n['title']}")
            print(f"   链接: {n['url']}")

    # 标记已推送
    if args.mark and new_notices:
        mark_as_pushed(new_notices, record_file)
        print(f"\n✅ 已将 {len(new_notices)} 条新通知标记为已推送。")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
