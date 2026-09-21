# AstrBot FutureTask 配置指南

FutureTask（主动任务）是 AstrBot 提供的定时任务机制，可以在指定时间唤醒一个 AI Agent 并执行预设指令。

## 前置条件

1. AstrBot 已成功安装并运行
2. AstrBot 已接入大模型（如 河图 / OpenAI / 通义千问 等）
3. MCP 功能已在 AstrBot 中启用

---

## 第一步：在 AstrBot 中配置 MCP Server

### 方法 A：通过 AstrBot 管理后台界面配置（推荐）

1. 打开 AstrBot 管理后台（通常是 `http://localhost:6185` 或你配置的端口）
2. 进入「MCP」或「工具」管理页面
3. 添加一个新的 MCP Server，填写：

   | 字段 | 值 |
   |------|-----|
   | 名称 | `cqupt-notice` |
   | 传输方式 | `stdio` |
   | 命令 | `python` |
   | 参数 | `["/path/to/cqupt-notice-pusher/mcp_server.py", "mcp"]` |

   > ⚠️ `/path/to/` 替换为你实际放置 `mcp_server.py` 的绝对路径。
   > Windows 路径示例：`E:\\cqupt-notice-pusher\\mcp_server.py`

4. 保存并启用

### 方法 B：编辑 AstrBot 配置文件

在 AstrBot 的配置文件中找到 MCP 相关配置，添加：

```json
{
  "mcp_servers": [
    {
      "name": "cqupt-notice",
      "transport": "stdio",
      "command": "python",
      "args": ["/path/to/cqupt-notice-pusher/mcp_server.py", "mcp"]
    }
  ]
}
```

### 验证 MCP 是否连接成功

在 AstrBot 日志中看到类似以下输出即表示成功：

```
[INFO] MCP server cqupt-notice connected
[INFO] Registered tool: get_latest_notices
```

---

## 第二步：创建 FutureTask（主动任务）

1. 在 AstrBot 管理后台进入「主动任务」或「FutureTask」页面
2. 点击「新建任务」
3. 填写任务配置：

   | 字段 | 值 |
   |------|-----|
   | 任务名称 | `重邮教务处通知早报` |
   | 执行时间 | 每天 `08:00` |
   | 投递目标 | 你的 QQ 私聊（或群聊） |
   | 系统提示词 | 见 `system_prompt.md` |

4. 保存并启用任务

---

## 第三步：测试

### 手动触发测试

1. 在 FutureTask 列表中找到刚创建的任务
2. 点击「立即执行」或「测试运行」
3. 观察：
   - AstrBot 日志中应出现调用 `get_latest_notices` 的记录
   - 你的 QQ 应收到推送消息

### 验证推送内容

收到的消息应类似：

```
🌅 早安！今天是 9 月 21 日，以下是教务处最新通知：

📋 通知1：《关于开展2026年首次招生专业申请学士学位授权申报工作的通知》
   重要程度：⭐⭐
   比赛建议：—
   截止日期：见原文
   🔗 原文链接：https://jw.cqupt.edu.cn/info/1012/69051.htm

—— 重邮教务处通知早报
```

---

## 常见问题

### Q: 提示 "MCP tool not found: get_latest_notices"

A: 检查 MCP Server 是否启动成功。先在命令行运行：
```bash
python mcp_server.py
```
确认能正常爬取后，再检查 AstrBot 的 MCP 配置路径是否正确。

### Q: 推送内容为空 / 没有新通知

A: 这是正常的。如果当天确实没有新通知，或所有通知都已推送过，会回复"今天教务处没有新通知"。
可删除 `pushed_records.json` 后重新测试去重效果。

### Q: 爬虫返回空列表

A: 可能原因：
1. WAF 拦截 —— 检查 Chrome 是否正常启动，尝试将 `headless` 设为 `false` 观察
2. 页面结构变化 —— 教务处改版后 HTML 结构可能变化，需更新解析逻辑
3. 网络问题 —— 服务器能否正常访问 `jw.cqupt.edu.cn`
