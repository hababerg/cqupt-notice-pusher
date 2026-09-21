# AstrBot 集成完整指南

本指南详细说明如何将 CQUPT 通知 MCP Server 接入 AstrBot，并设置定时推送。

## 前置条件

- ✅ AstrBot 已安装并能正常运行（参考 [AstrBot 官方文档](https://github.com/Soulter/AstrBot)）
- ✅ AstrBot 已配置好大模型 API（LLM）
- ✅ 本项目的爬虫已测试通过（`python tests/test_crawler.py` 能正常返回通知）
- ✅ `pip install -r requirements.txt` 已执行（特别是 `mcp` 包）

---

## 两种接入方式

AstrBot 支持两种 MCP 传输方式，根据你的部署场景选择：

| 方式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **stdio** | MCP Server 和 AstrBot 在同一台机器 | 配置简单，无需端口 | 必须同机部署 |
| **streamable-http** | MCP Server 和 AstrBot 在不同机器 | 可远程部署，灵活 | 需要开放端口 |

> 💡 **推荐**：如果 AstrBot 和爬虫在同一台服务器，用 **stdio** 最简单。
> 如果爬虫在本地、AstrBot 在云端，用 **streamable-http**。

---

## 方式一：stdio 传输（推荐同机使用）

### 1. 确认 MCP Server 能启动

```bash
# 先测试脚本能正常运行（不需要 mcp 子命令）
python mcp_server.py --no-mark

# 确认无误后，测试 MCP 模式能否启动（会阻塞，Ctrl+C 退出）
python mcp_server.py mcp
```

如果看到类似 `MCP Server running` 的日志说明正常。

### 2. 在 AstrBot 中添加 MCP Server

#### 方法 A：通过 AstrBot 管理后台（推荐）

1. 打开 AstrBot 管理后台（默认 `http://localhost:6185`）
2. 左侧菜单找到 **「MCP」** 或 **「工具扩展」**
3. 点击 **「添加 MCP 服务器」**
4. 填写配置：

   | 字段 | 填写内容 |
   |------|----------|
   | 名称 | `cqupt-notice` |
   | 传输方式 | `stdio` |
   | 启动命令 | `python` |
   | 命令参数 | `["/你的绝对路径/mcp_server.py", "mcp"]` |

   > ⚠️ **路径必须是绝对路径**
   >
   > - Windows 示例：`E:\projects\cqupt-notice-pusher\mcp_server.py`
   > - Linux 示例：`/home/ubuntu/cqupt-notice-pusher/mcp_server.py`
   >
   > 如果用了虚拟环境，启动命令改为虚拟环境的 python 路径：
   > - Windows：`E:\projects\cqupt-notice-pusher\venv\Scripts\python.exe`
   > - Linux：`/home/ubuntu/cqupt-notice-pusher/venv/bin/python`

5. 点击 **「保存」** 或 **「连接」**

#### 方法 B：编辑 AstrBot 配置文件

找到 AstrBot 的配置文件（通常是 `data/cmd_config.json` 或 `config.json`），
在 MCP 配置部分添加：

```json
{
  "mcp": {
    "enabled": true,
    "servers": [
      {
        "name": "cqupt-notice",
        "type": "stdio",
        "command": "python",
        "args": ["/你的绝对路径/mcp_server.py", "mcp"]
      }
    ]
  }
}
```

保存后重启 AstrBot。

### 3. 验证连接成功

在 AstrBot 日志中搜索以下关键词：

```
✅ MCP 服务器 cqupt-notice 连接成功
已注册工具: get_latest_notices
已注册工具: get_notice_count
```

如果看到工具注册成功，说明 MCP 已接入。

---

## 方式二：streamable-http 传输（跨机器使用）

### 1. 启动 MCP Server（HTTP 模式）

```bash
# 在 MCP Server 所在机器上启动
python mcp_server.py mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

启动成功后会看到：

```
INFO: MCP Server running on http://0.0.0.0:8000
```

> 💡 可以用 `nohup` 或 systemd 让它后台常驻运行。
> 确保防火墙开放了 8000 端口（仅对 AstrBot 所在 IP 开放）。

### 2. 在 AstrBot 中添加 MCP Server

1. 打开 AstrBot 管理后台 → MCP 管理
2. 添加 MCP 服务器：

   | 字段 | 填写内容 |
   |------|----------|
   | 名称 | `cqupt-notice` |
   | 传输方式 | `streamable-http`（或 `http`） |
   | URL | `http://MCP服务器IP:8000/mcp` |

   > 具体 URL 路径取决于你的 FastMCP 版本，常见的有：
   > - `http://IP:8000/mcp`
   > - `http://IP:8000/`
   >
   > 如果连接失败，可在 MCP Server 启动日志中查看实际暴露的路径。

3. 保存并连接

---

## 第三步：配置定时推送（FutureTask）

### 1. 打开 FutureTask 管理

在 AstrBot 管理后台找到 **「主动任务」** 或 **「FutureTask」** 菜单。

### 2. 创建新任务

点击 **「新建任务」**，填写：

| 字段 | 填写内容 |
|------|----------|
| 任务名称 | `重邮教务处通知早报` |
| 触发类型 | `定时` / `cron` |
| Cron 表达式 | `0 0 8 * * ?` （每天早上 8 点） |
| 投递目标 | 你的 QQ 号（私聊）或群号 |
| 系统提示词 | 见下方 |

#### 系统提示词（完整复制）

```
你是一个「重庆邮电大学教务处通知推送助手」。你的职责是每天定时获取教务处最新通知，
分析每条通知的重要性，并以友好、简洁的格式推送给用户。

## 工作流程
1. 调用 MCP 工具 get_latest_notices 获取当天的最新通知列表。
2. 对每条通知进行分析：
   - 重要程度：判断这条通知对普通本科生是否重要（高/中/低）
   - 比赛建议：如果是比赛/竞赛通知，判断是否值得参加（结合门槛、收益、时间成本）
   - 关键信息：提取截止日期、报名链接、地点等
3. 按固定格式生成推送文案。

## 推送文案格式
🌅 早安！今天是 X 月 X 日，以下是教务处最新通知：

📋 通知1：《通知标题》
   重要程度：⭐⭐⭐
   比赛建议：值得参加/不建议参加（简述理由）
   截止日期：XXXX-XX-XX（如无法确定则写"见原文"）
   🔗 原文链接：https://...

📋 通知2：...

—— 重邮教务处通知早报

## 规则
- 如果当天没有新通知，回复：「今天教务处没有新通知哦～」
- 重要程度用 ⭐ 表示，高=3颗，中=2颗，低=1颗
- 比赛建议只对竞赛类通知给出，非竞赛类写「—」
- 保持语气友好、简洁
- 所有链接必须完整保留
```

### 3. 保存并启用

点击保存，确保任务状态为 **已启用**。

---

## 第四步：测试

### 测试 1：手动触发任务

1. 在 FutureTask 列表中找到「重邮教务处通知早报」
2. 点击 **「立即执行」** 或 **「运行一次」**
3. 观察 AstrBot 日志，应看到：
   ```
   [FutureTask] 触发任务: 重邮教务处通知早报
   [MCP] 调用工具: get_latest_notices
   [LLM] 生成回复...
   ```
4. 你的 QQ 应收到推送消息 ✅

### 测试 2：在对话中直接调用工具

在与 AstrBot 的对话中发送：

```
调用 get_latest_notices 工具，看看今天有什么通知
```

如果 AstrBot 能返回通知列表，说明 MCP 工具调用正常。

### 测试 3：验证去重

连续手动触发两次任务：
- 第一次：应返回当天通知
- 第二次：应回复"今天教务处没有新通知"（因为已推送过）

如果想重新测试，删除 `pushed_records.json` 即可。

---

## 常见问题排查

### ❌ MCP 连接失败 / 工具不显示

1. **检查 MCP Server 能否独立启动**
   ```bash
   python mcp_server.py mcp
   ```
   如果报错，先解决报错。

2. **检查路径是否正确**
   - 必须是**绝对路径**
   - 路径中的空格需要正确处理

3. **检查 Python 环境**
   - AstrBot 调用的 `python` 和你安装依赖的 `python` 是同一个吗？
   - 建议在 AstrBot MCP 配置中直接写虚拟环境的 python 绝对路径

4. **查看 AstrBot 日志**
   - 日志中会有 MCP 连接的详细错误信息
   - 常见错误：`command not found`、`No module named 'mcp'`、`No module named 'DrissionPage'`

### ❌ 调用工具后没有返回通知

1. 先运行 `python mcp_server.py --no-mark` 看爬虫是否正常
2. 检查 `pushed_records.json` —— 如果通知都已推送过，会返回空
3. 检查 `config.json` 中 `days_to_fetch` 是否设得太小

### ❌ 推送内容格式不对

1. 检查系统提示词是否完整复制
2. 不同大模型对格式的遵循程度不同，可在提示词中强调"严格按照格式输出"

### ❌ FutureTask 到点不触发

1. 检查 AstrBot 的时区设置是否正确
2. 检查 Cron 表达式是否正确
3. 查看 AstrBot 日志中是否有 FutureTask 相关错误

---

## 进阶：MCP Server 常驻运行（HTTP 模式）

如果使用 streamable-http 方式，建议用 systemd 让 MCP Server 常驻运行。

创建 `/etc/systemd/system/cqupt-mcp.service`：

```ini
[Unit]
Description=CQUPT Notice MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/cqupt-notice-pusher
ExecStart=/home/ubuntu/cqupt-notice-pusher/venv/bin/python mcp_server.py mcp --transport streamable-http --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable cqupt-mcp
sudo systemctl start cqupt-mcp
sudo systemctl status cqupt-mcp
```
