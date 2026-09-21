# CQUPT 教务处通知爬取与 AI 推送系统

> 基于 **DrissionPage + MCP + AstrBot** 的重庆邮电大学教务处通知自动爬取、AI 分析与 QQ 推送系统。
>
> 每天早上 8 点，自动抓取教务处最新通知，由 AI 分析重要性并生成友好文案推送到你的 QQ。

---

## 📋 目录

- [系统架构](#系统架构)
- [技术选型与原理](#技术选型与原理)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
  - [第一步：安装依赖](#第一步安装依赖)
  - [第二步：测试爬虫](#第二步测试爬虫)
  - [第三步：配置 MCP Server](#第三步配置-mcp-server)
  - [第四步：接入 AstrBot](#第四步接入-astrbot)
  - [第五步：设置定时推送](#第五步设置定时推送)
- [配置说明](#配置说明)
- [去重机制](#去重机制)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [许可证](#许可证)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AstrBot (QQ 机器人)                      │
│                                                             │
│  ┌──────────┐    调用工具     ┌──────────────────────┐      │
│  │ FutureTask│ ──────────────▶│  MCP Client (内置)    │      │
│  │ (定时任务) │                └──────────┬───────────┘      │
│  └──────────┘                           │                   │
│       ▲                                  │ HTTP/STDIO        │
│       │ 推送                            ▼                   │
│  ┌────┴─────┐                   ┌──────────────────┐       │
│  │  AI Agent │ ◀── 通知数据 ──── │  MCP Server       │       │
│  │ (大模型)  │                   │  (get_latest_notices) │  │
│  └────┬─────┘                   └────────┬─────────┘       │
│       │ 生成文案                          │ 爬取            │
│       ▼                                   ▼                 │
│  ┌─────────┐                   ┌──────────────────┐       │
│  │ QQ 推送  │                   │ DrissionPage     │       │
│  └─────────┘                   │ + Chrome         │       │
│                                └────────┬─────────┘       │
└─────────────────────────────────────────┼───────────────────┘
                                          ▼
                              https://jw.cqupt.edu.cn/tzgg.htm
```

### 工作流程

1. **定时触发**：AstrBot 的 FutureTask 每天 08:00 唤醒 AI Agent
2. **调用工具**：Agent 调用 MCP 工具 `get_latest_notices`
3. **爬取解析**：MCP Server 用 DrissionPage 绕过 WAF 爬取通知，解析后去重
4. **AI 分析**：大模型分析每条通知的重要性、比赛建议、关键信息
5. **QQ 推送**：生成友好文案推送到 QQ

---

## 技术选型与原理

### 为什么用 DrissionPage 而不是 requests？

目标页面 `jw.cqupt.edu.cn` 使用了 **加速乐 WAF**，首次访问会返回 JS 挑战页面（HTTP 412），
要求浏览器执行 JS 计算后才能获得真实内容。

| 方案 | 结果 | 原因 |
|------|------|------|
| `requests` / `httpx` | ❌ 失败 | 无法执行 JS，只能拿到挑战页 |
| `cloudscraper` | ❌ 失败 | 新版加速乐防护已升级，旧绕过手段失效 |
| `Playwright` | ❌ 失败 | 使用 CDP 协议，自动化特征明显，被 WAF 识别 |
| **DrissionPage + Chrome** | ✅ 成功 | 通过启动参数隐藏自动化特征 |

### DrissionPage 反检测原理

启动 Chrome 时传入两个关键参数：

```python
co.set_argument("--disable-blink-features=AutomationControlled")  # 移除 navigator.webdriver 标识
co.set_argument("--headless=new")                                  # 新版无头模式，更接近真实浏览器
```

这样 WAF 的 JS 检测脚本执行时，`navigator.webdriver` 返回 `undefined`（而非 `true`），
浏览器指纹看起来像真实用户，从而通过挑战、获得有效 Cookie。

### 为什么用 MCP？

MCP（Model Context Protocol）是 AstrBot 官方推荐的外部工具扩展方式。
它把"爬取通知"这个能力封装成标准化工具 `get_latest_notices`，让 AI Agent 可以像调用函数一样调用它。

---

## 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | >= 3.10 | |
| Chrome / Chromium | >= 100 | DrissionPage 会自动调用系统 Chrome |
| AstrBot | 最新版 | QQ 机器人框架，需支持 MCP |
| 大模型 API | 任意 | 如 河图、OpenAI、通义千问等 |

> 💡 Chrome 只需正常安装即可，DrissionPage 会自动查找。
> 如果自动查找失败，可在 `config.json` 中指定 `chrome_path`。

---

## 快速开始

### 第一步：安装依赖

```bash
# 1. 克隆本项目
git clone https://github.com/你的用户名/cqupt-notice-pusher.git
cd cqupt-notice-pusher

# 2. 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 第二步：测试爬虫

在接入 AstrBot 之前，先独立测试爬虫是否正常工作：

```bash
# 基本测试（爬取当天通知，不标记已推送）
python tests/test_crawler.py

# 查看页面上所有通知（不按日期过滤）
python tests/test_crawler.py --all

# 有头模式（能看到浏览器操作，便于调试）
python tests/test_crawler.py --no-head

# 爬取最近 3 天的通知
python tests/test_crawler.py --days 3
```

✅ **预期输出**：

```
============================================================
  CQUPT 教务处通知爬虫 - 独立测试
============================================================
目标 URL : https://jw.cqupt.edu.cn/tzgg.htm
无头模式 : True
日期范围 : 最近 1 天
============================================================

[1/4] 正在爬取页面...
✅ 爬取成功，HTML 长度: 12345

[2/4] 正在解析通知列表...
✅ 解析到 20 条通知

[3/4] 日期过滤（最近 1 天）...
✅ 过滤后剩余 3 条通知

[4/4] 去重检查...
   已推送记录: 0 条
✅ 去重后剩余 3 条新通知

============================================================
  爬取结果
============================================================

1. [2026-09-21] 🆕 新
   标题: 关于XXX的通知
   链接: https://jw.cqupt.edu.cn/info/1012/69051.htm

...
```

> ⚠️ 如果爬虫失败，请先参考 [常见问题](#常见问题) 排查。

### 第三步：配置 MCP Server

1. 复制配置文件模板：

```bash
cp config.example.json config.json
```

2. 编辑 `config.json`（通常无需修改，默认即可）：

```json
{
  "target_url": "https://jw.cqupt.edu.cn/tzgg.htm",
  "days_to_fetch": 1,
  "headless": true,
  "chrome_path": null,
  "record_file": "pushed_records.json",
  "page_load_timeout": 30
}
```

3. 测试 MCP Server 能否正常启动：

```bash
python mcp_server.py
```

这条命令会直接运行爬取并打印结果（不会启动 MCP 服务）。
要作为 MCP Server 运行，需要通过 AstrBot 来启动，见下一步。

### 第四步：接入 AstrBot

1. 确保 AstrBot 已安装并能正常运行

2. 在 AstrBot 管理后台添加 MCP Server：

   | 字段 | 值 |
   |------|-----|
   | 名称 | `cqupt-notice` |
   | 传输方式 | `stdio` |
   | 命令 | `python` |
   | 参数 | `["/你的路径/cqupt-notice-pusher/mcp_server.py", "mcp"]` |

   > Windows 路径示例：`E:\\projects\\cqupt-notice-pusher\\mcp_server.py`
   > Linux 路径示例：`/home/user/cqupt-notice-pusher/mcp_server.py`

3. 保存并启用 MCP Server

4. 在 AstrBot 日志中确认连接成功：
   ```
   [INFO] MCP server cqupt-notice connected
   [INFO] Registered tool: get_latest_notices
   ```

> 📖 详细的 MCP 配置方法见 [`astrbot/future_task_guide.md`](astrbot/future_task_guide.md)

### 第五步：设置定时推送

1. 在 AstrBot 管理后台进入「主动任务」/「FutureTask」页面

2. 新建任务：

   | 字段 | 值 |
   |------|-----|
   | 任务名称 | `重邮教务处通知早报` |
   | 执行时间 | 每天 `08:00` |
   | 投递目标 | 你的 QQ（私聊或群聊） |
   | 系统提示词 | 见下方 |

3. 系统提示词（复制 [`astrbot/system_prompt.md`](astrbot/system_prompt.md) 的内容）：

   ```
   你是一个「重庆邮电大学教务处通知推送助手」。你的职责是每天定时获取教务处最新通知，
   分析每条通知的重要性，并以友好、简洁的格式推送给用户。

   工作流程：
   1. 调用 MCP 工具 get_latest_notices 获取当天的最新通知列表
   2. 对每条通知分析：重要程度（高/中/低）、比赛建议、关键信息
   3. 按固定格式生成推送文案

   推送文案格式：
   🌅 早安！今天是 X 月 X 日，以下是教务处最新通知：

   📋 通知1：《通知标题》
      重要程度：⭐⭐⭐
      比赛建议：值得参加 / 不建议参加
      截止日期：XXXX-XX-XX
      🔗 原文链接：https://...

   —— 重邮教务处通知早报
   ```

4. 保存并启用任务

5. **测试**：点击「立即执行」，你的 QQ 应收到推送消息 🎉

---

## 配置说明

`config.json` 各字段说明：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_url` | string | `https://jw.cqupt.edu.cn/tzgg.htm` | 通知公告页 URL |
| `days_to_fetch` | int | `1` | 抓取最近 N 天的通知（1 = 仅当天） |
| `headless` | bool | `true` | 是否无头模式运行 Chrome |
| `chrome_path` | string/null | `null` | Chrome 可执行文件路径，null 为自动查找 |
| `record_file` | string | `pushed_records.json` | 已推送记录文件路径 |
| `page_load_timeout` | int | `30` | 页面加载超时（秒） |

---

## 去重机制

为避免重复推送同一条通知，系统维护一份已推送记录文件 `pushed_records.json`：

- 每次爬取后，对比通知 URL 是否已推送过
- 只返回**未推送过**的通知
- `get_latest_notices` 被调用后，自动将返回的通知标记为已推送

### 重置去重记录

如果需要重新推送所有通知，删除 `pushed_records.json` 即可：

```bash
rm pushed_records.json   # Linux / macOS
del pushed_records.json  # Windows
```

---

## 常见问题

### Q: 爬虫返回空列表 / 爬取失败

**可能原因 & 解决方案：**

1. **WAF 拦截**
   - 将 `config.json` 中 `headless` 设为 `false`，观察浏览器是否被拦截
   - 确认 Chrome 版本 >= 100

2. **页面结构变化**
   - 教务处改版后 HTML 结构可能变化
   - 用 `python tests/test_crawler.py --no-head` 打开浏览器检查页面
   - 根据实际 HTML 调整 `mcp_server.py` 中的 `parse_notices` 函数

3. **网络问题**
   - 确认服务器能正常访问 `jw.cqupt.edu.cn`
   - `curl https://jw.cqupt.edu.cn/tzgg.htm` 测试连通性

### Q: MCP 工具在 AstrBot 中找不到

1. 先在命令行运行 `python mcp_server.py` 确认脚本无报错
2. 检查 AstrBot MCP 配置中的路径是否为**绝对路径**
3. 检查 AstrBot 日志中是否有 MCP 连接错误
4. 确认 `mcp` 包已安装：`pip show mcp`

### Q: 推送内容为空

这是正常现象。如果当天没有新通知，或所有通知都已推送过，AI 会回复
"今天教务处没有新通知哦～"。

可删除 `pushed_records.json` 后重新测试。

### Q: DrissionPage 找不到 Chrome

在 `config.json` 中手动指定 Chrome 路径：

```json
{
  "chrome_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
}
```

常见 Chrome 路径：
- Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe`
- macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Linux: `/usr/bin/google-chrome` 或 `/usr/bin/chromium-browser`

---

## 项目结构

```
cqupt-notice-pusher/
├── README.md                    # 本文件，完整教程
├── mcp_server.py                # MCP Server 主程序（爬虫 + 解析 + 去重 + 工具）
├── requirements.txt             # Python 依赖
├── config.example.json          # 配置模板（复制为 config.json 使用）
├── .gitignore
├── astrbot/
│   ├── system_prompt.md         # AstrBot AI Agent 系统提示词
│   └── future_task_guide.md     # FutureTask 详细配置指南
└── tests/
    └── test_crawler.py          # 独立爬虫测试脚本
```

---

## 许可证

MIT License

---

## 致谢

- [DrissionPage](https://github.com/g1879/DrissionPage) - 强大的 Python 浏览器自动化库
- [AstrBot](https://github.com/Soulter/AstrBot) - 多平台 QQ 机器人框架
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol

> 本项目仅供学习交流使用，请遵守学校网站的使用条款，不要对目标网站造成过大压力。
