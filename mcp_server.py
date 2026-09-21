"""
CQUPT 教务处通知 MCP Server
=================================
通过 DrissionPage 绕过加速乐 WAF 爬取重庆邮电大学教务处通知公告，
封装为 MCP 工具供 AstrBot 的 AI Agent 调用。

功能：
  - 爬取 https://jw.cqupt.edu.cn/tzgg.htm 通知列表
  - 解析标题、链接、日期
  - 按日期过滤（默认当天）
  - 基于已推送记录去重
  - 暴露 MCP 工具 get_latest_notices
"""

import json
import os
import re
import sys
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path

from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cqupt-notice-mcp")

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
PUSHED_RECORDS_PATH = BASE_DIR / "pushed_records.json"

TARGET_URL = "https://jw.cqupt.edu.cn/tzgg.htm"

# 默认配置（当 config.json 不存在时使用）
DEFAULT_CONFIG = {
    "target_url": TARGET_URL,
    "days_to_fetch": 1,            # 抓取最近 N 天的通知（1 = 仅当天）
    "headless": True,              # 是否无头模式运行 Chrome
    "chrome_path": None,           # Chrome 可执行文件路径，None 为自动查找
    "record_file": str(PUSHED_RECORDS_PATH),
    "page_load_timeout": 30,       # 页面加载超时（秒）
}


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """加载配置文件，不存在则使用默认配置并创建示例文件。"""
    if not CONFIG_PATH.exists():
        logger.warning("未找到 config.json，使用默认配置。已生成 config.example.json 供参考。")
        example_path = BASE_DIR / "config.example.json"
        if not example_path.exists():
            example_path.write_text(
                json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 用默认值补全缺失字段
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    except Exception as e:
        logger.error(f"读取 config.json 失败: {e}，使用默认配置。")
        return DEFAULT_CONFIG.copy()


# ---------------------------------------------------------------------------
# 已推送记录管理（去重）
# ---------------------------------------------------------------------------
def load_pushed_records(record_file: str) -> Dict[str, str]:
    """加载已推送记录，返回 {url: title} 字典。"""
    path = Path(record_file)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取已推送记录失败: {e}")
        return {}


def save_pushed_records(records: Dict[str, str], record_file: str) -> None:
    """保存已推送记录。"""
    path = Path(record_file)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存已推送记录失败: {e}")


def mark_as_pushed(notices: List[Dict], record_file: str) -> None:
    """将通知标记为已推送。"""
    records = load_pushed_records(record_file)
    for n in notices:
        records[n["url"]] = n["title"]
    save_pushed_records(records, record_file)
    logger.info(f"已将 {len(notices)} 条通知标记为已推送。")


# ---------------------------------------------------------------------------
# 爬取核心
# ---------------------------------------------------------------------------
def build_chromium_options(config: dict) -> ChromiumOptions:
    """构建 DrissionPage 的 Chromium 启动选项，隐藏自动化特征以绕过 WAF。"""
    co = ChromiumOptions()

    # 关键反检测参数：移除 navigator.webdriver 标识
    co.set_argument("--disable-blink-features=AutomationControlled")

    # 新版无头模式，更接近真实浏览器
    if config.get("headless", True):
        co.set_argument("--headless=new")

    # 禁用自动化扩展 / 提示条
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-infobars")
    co.set_argument("--window-size=1920,1080")

    # 指定 Chrome 路径（可选）
    chrome_path = config.get("chrome_path")
    if chrome_path:
        co.set_browser_path(chrome_path)

    return co


def fetch_page_html(url: str, config: dict) -> Optional[str]:
    """使用 DrissionPage 访问页面并返回 HTML。"""
    page = None
    try:
        co = build_chromium_options(config)
        page = ChromiumPage(co)
        page.set.timeouts(config.get("page_load_timeout", 30))
        logger.info(f"正在访问: {url}")
        page.get(url)
        # 等待页面主体加载（列表出现）
        page.wait.doc_loaded()
        html = page.html
        logger.info(f"页面获取成功，HTML 长度: {len(html)}")
        return html
    except Exception as e:
        logger.error(f"页面获取失败: {e}")
        return None
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 解析通知列表
# ---------------------------------------------------------------------------
def parse_notices(html: str, base_url: str = "https://jw.cqupt.edu.cn") -> List[Dict]:
    """
    解析通知公告页 HTML，返回通知列表。

    页面结构（实测）：
      <li>
        <h3><a href="...">通知标题</a></h3>
        <span class="date">[2026-09-20]</span>  或  <a>2026-09-20</a>
      </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    notices = []

    # 策略 1：查找所有包含日期格式文本的列表项
    date_pattern = re.compile(r"(20\d{2}-\d{2}-\d{2})")

    # 遍历所有 <li>，寻找包含标题链接 + 日期的项
    for li in soup.find_all("li"):
        # 找标题链接
        title_link = None
        # 优先 h3 > a，其次 a
        h3 = li.find("h3")
        if h3:
            title_link = h3.find("a", href=True)
        if not title_link:
            title_link = li.find("a", href=True)

        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")

        # 找日期
        date_str = None
        # 方式 A：li 内文本中正则匹配
        li_text = li.get_text()
        m = date_pattern.search(li_text)
        if m:
            date_str = m.group(1)
        else:
            # 方式 B：查找带日期的 span / a
            for tag in li.find_all(["span", "a", "div", "p"]):
                tm = date_pattern.search(tag.get_text())
                if tm:
                    date_str = tm.group(1)
                    break

        if not title or not date_str:
            continue

        # 补全相对链接
        if href.startswith("/"):
            full_url = base_url + href
        elif href.startswith("http"):
            full_url = href
        elif href.startswith("content.jsp"):
            full_url = base_url + "/" + href
        else:
            full_url = base_url + "/" + href

        notices.append({
            "title": title,
            "url": full_url,
            "date": date_str,
        })

    # 去重（同一 URL 可能被多个策略匹配到）
    seen = set()
    unique = []
    for n in notices:
        if n["url"] not in seen:
            seen.add(n["url"])
            unique.append(n)

    logger.info(f"解析到 {len(unique)} 条通知。")
    return unique


# ---------------------------------------------------------------------------
# 过滤与去重
# ---------------------------------------------------------------------------
def filter_by_date(notices: List[Dict], days: int = 1) -> List[Dict]:
    """只保留最近 days 天内的通知。"""
    today = date.today()
    result = []
    for n in notices:
        try:
            d = datetime.strptime(n["date"], "%Y-%m-%d").date()
            if (today - d).days < days:
                result.append(n)
        except ValueError:
            continue
    return result


def filter_unpushed(notices: List[Dict], record_file: str) -> List[Dict]:
    """过滤掉已经推送过的通知。"""
    records = load_pushed_records(record_file)
    return [n for n in notices if n["url"] not in records]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def get_latest_notices_impl(config: Optional[dict] = None) -> List[Dict]:
    """
    完整流程：爬取 -> 解析 -> 日期过滤 -> 去重。
    返回未推送过的最新通知列表。
    """
    if config is None:
        config = load_config()

    url = config.get("target_url", TARGET_URL)
    days = config.get("days_to_fetch", 1)
    record_file = config.get("record_file", str(PUSHED_RECORDS_PATH))

    html = fetch_page_html(url, config)
    if not html:
        logger.error("未能获取页面 HTML，返回空列表。")
        return []

    notices = parse_notices(html)
    if not notices:
        logger.warning("未解析到任何通知，请检查页面结构是否变化。")
        return []

    # 按日期过滤
    recent = filter_by_date(notices, days)
    logger.info(f"日期过滤后剩余 {len(recent)} 条通知（最近 {days} 天）。")

    # 去重
    new_notices = filter_unpushed(recent, record_file)
    logger.info(f"去重后剩余 {len(new_notices)} 条新通知。")

    return new_notices


# ---------------------------------------------------------------------------
# MCP Server 定义
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(name="cqupt-notice-pusher")

    @mcp.tool()
    def get_latest_notices() -> str:
        """
        获取重庆邮电大学教务处最新通知（已去重）。

        返回值说明：
          - 一个 JSON 字符串，包含通知列表，每条通知有 title / url / date 字段。
          - 如果当天没有新通知，返回空列表的 JSON。
        """
        config = load_config()
        notices = get_latest_notices_impl(config)
        # 标记为已推送（调用即视为已推送，避免重复）
        if notices:
            mark_as_pushed(notices, config.get("record_file", str(PUSHED_RECORDS_PATH)))
        return json.dumps(notices, ensure_ascii=False)

    @mcp.tool()
    def get_notice_count() -> str:
        """返回当前已推送通知的总数，用于排查去重是否正常工作。"""
        config = load_config()
        records = load_pushed_records(config.get("record_file", str(PUSHED_RECORDS_PATH)))
        return json.dumps({"pushed_count": len(records)}, ensure_ascii=False)

except ImportError:
    logger.warning(
        "未安装 mcp 包，MCP 工具未注册。"
        "如需作为 MCP Server 运行，请执行: pip install mcp"
    )
    mcp = None


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def run_mcp_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000):
    """
    启动 MCP Server。

    transport 可选值:
      - stdio            : 标准输入输出（AstrBot 本地调用推荐）
      - streamable-http  : HTTP 流式传输（AstrBot 远程调用推荐）
      - sse              : Server-Sent Events
    """
    if mcp is None:
        logger.error("MCP 未初始化，请先安装 mcp 包: pip install mcp")
        sys.exit(1)

    logger.info(f"启动 MCP Server (transport={transport}, host={host}, port={port})")

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in ("streamable-http", "sse", "http"):
        mcp.run(transport=transport, host=host, port=port)
    else:
        logger.error(f"不支持的 transport: {transport}")
        sys.exit(1)


def main():
    """
    直接运行本脚本可测试爬取与解析（无需 MCP 环境）：
        python mcp_server.py
    """
    import argparse

    parser = argparse.ArgumentParser(description="CQUPT 教务处通知爬取 / MCP Server")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- mcp 子命令：启动 MCP Server ----
    mcp_parser = subparsers.add_parser("mcp", help="启动 MCP Server")
    mcp_parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse", "http"],
                            default="stdio", help="传输方式（默认 stdio）")
    mcp_parser.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址（默认 127.0.0.1）")
    mcp_parser.add_argument("--port", type=int, default=8000, help="HTTP 监听端口（默认 8000）")

    # ---- 默认：爬取测试 ----
    parser.add_argument("--no-mark", action="store_true",
                        help="测试模式：不标记为已推送")
    parser.add_argument("--days", type=int, default=None,
                        help="覆盖配置中的 days_to_fetch")

    args = parser.parse_args()

    if args.command == "mcp":
        run_mcp_server(transport=args.transport, host=args.host, port=args.port)
        return

    # 默认行为：爬取测试
    config = load_config()
    if args.days is not None:
        config["days_to_fetch"] = args.days

    notices = get_latest_notices_impl(config)

    if not notices:
        print("\n[结果] 没有新通知。")
        return

    print(f"\n[结果] 共 {len(notices)} 条新通知：\n")
    for i, n in enumerate(notices, 1):
        print(f"{i}. [{n['date']}] {n['title']}")
        print(f"   链接: {n['url']}")

    if not args.no_mark:
        mark_as_pushed(notices, config.get("record_file", str(PUSHED_RECORDS_PATH)))
        print("\n已标记为已推送。（使用 --no-mark 可仅测试不标记）")


if __name__ == "__main__":
    main()
