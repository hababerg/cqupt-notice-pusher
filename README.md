# CQUPT 教务处通知推送

基于 `DrissionPage`、`MCP` 和 `AstrBot` 的重庆邮电大学教务处通知自动抓取与 QQ 推送工具。

它会：

1. 使用 Chrome 访问教务处通知页；
2. 解析通知标题、日期和链接；
3. 按日期筛选，并根据记录文件去重；
4. 通过 MCP 提供给 AstrBot；
5. 由大模型分析后，通过 FutureTask 定时推送。

## 项目结构

```text
cqupt-notice-pusher/
├── mcp_server.py              # 爬虫、去重和 MCP Server
├── config.example.json        # 配置模板
├── requirements.txt           # Python 依赖
├── tests/
│   ├── test_crawler.py        # 需要 Chrome 和网络的手动爬虫测试
│   └── test_unit.py           # 不联网的核心逻辑测试
├── deploy/
│   └── cqupt-mcp.service.example # Linux systemd 模板
└── astrbot/
    ├── system_prompt.md       # AstrBot 推送提示词
    └── future_task_guide.md   # AstrBot 配置指南
```

## 环境要求

- Python 3.10 或更高版本
- Chrome 或 Chromium 100+
- AstrBot（只有接入 QQ 推送时需要）
- 可访问 `https://jw.cqupt.edu.cn/tzgg.htm` 的网络环境

## 安装

```bash
git clone https://github.com/Habapure/cqupt-notice-pusher.git
cd cqupt-notice-pusher

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

复制配置模板：

```bash
# Windows PowerShell
Copy-Item config.example.json config.json

# Linux / macOS
cp config.example.json config.json
```

没有 `config.json` 时，程序会使用内置默认配置。

### Ubuntu / Debian 额外准备

Linux 无头模式需要安装 Chrome 或 Chromium。Ubuntu/Debian 可执行：

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip chromium
```

确认浏览器路径：

```bash
which chromium
which google-chrome
```

如果无法自动找到浏览器，在 `config.json` 中填写实际路径：

```json
{
  "chrome_path": "/usr/bin/chromium"
}
```

Linux 服务器建议保持无头模式：

```json
{
  "headless": true
}
```

程序已默认添加适合 Linux 服务器的 Chrome 启动参数。

## 配置

`config.json`：

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

| 配置项 | 说明 |
|---|---|
| `target_url` | 通知公告页地址 |
| `days_to_fetch` | 抓取最近几天，`1` 表示今天 |
| `headless` | 是否隐藏 Chrome 窗口 |
| `chrome_path` | Chrome 可执行文件路径，`null` 表示自动查找 |
| `record_file` | 已处理通知记录文件；相对路径相对于项目目录 |
| `page_load_timeout` | 页面加载超时秒数 |

## 本地测试

运行不联网的核心测试：

```bash
python -m unittest discover -s tests -p "test_unit.py"
```

运行实际爬虫：

```bash
# 抓取当天通知，不写入推送记录
python tests/test_crawler.py

# 抓取最近 3 天
python tests/test_crawler.py --days 3

# 显示所有通知
python tests/test_crawler.py --all

# 显示 Chrome 窗口，便于排查问题
python tests/test_crawler.py --no-head

# 写入已推送记录
python tests/test_crawler.py --mark
```

首次测试建议不要使用 `--mark`，确认结果正常后再写入记录。

## MCP Server

### stdio：AstrBot 同机部署

```bash
python mcp_server.py mcp
```

AstrBot 中添加 MCP Server 时，建议使用虚拟环境 Python 的绝对路径：

| 字段 | 示例 |
|---|---|
| 名称 | `cqupt-notice` |
| 传输方式 | `stdio` |
| 启动命令 | `E:\path\to\.venv\Scripts\python.exe` |
| 参数 | `["E:\path\to\mcp_server.py", "mcp"]` |

Linux 示例：

```text
/home/user/cqupt-notice-pusher/.venv/bin/python
["/home/user/cqupt-notice-pusher/mcp_server.py", "mcp"]
```

### streamable-http：跨机器部署

```bash
python mcp_server.py mcp `
  --transport streamable-http `
  --host 127.0.0.1 `
  --port 8000
```

Linux / macOS：

```bash
python mcp_server.py mcp \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8000
```

跨机器部署时，不要直接把服务暴露到公网。应通过防火墙、VPN 或反向代理限制访问来源。

当前提供的工具：

- `get_latest_notices`：获取日期范围内、尚未记录的通知；
- `get_notice_count`：查看已记录通知数量。

### Linux systemd 常驻运行

使用 [deploy/cqupt-mcp.service.example](deploy/cqupt-mcp.service.example) 模板：

```bash
sudo cp deploy/cqupt-mcp.service.example /etc/systemd/system/cqupt-mcp.service
sudo nano /etc/systemd/system/cqupt-mcp.service
```

修改用户名和项目路径：

```ini
User=你的Linux用户名
WorkingDirectory=/opt/cqupt-notice-pusher
ExecStart=/opt/cqupt-notice-pusher/.venv/bin/python /opt/cqupt-notice-pusher/mcp_server.py mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

然后启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cqupt-mcp
sudo systemctl status cqupt-mcp
```

查看实时日志：

```bash
journalctl -u cqupt-mcp -f
```

## 去重行为

默认使用项目目录下的 `pushed_records.json` 保存 URL 和标题。

`get_latest_notices` 在返回通知后会立即将它们写入记录。这适配 AstrBot 的定时任务模型，但意味着“工具调用成功”会被视为“已推送”。如果 AstrBot 在后续生成或发送消息时失败，通知不会自动重试。

需要重新测试时删除记录文件：

```bash
# Windows PowerShell
Remove-Item pushed_records.json

# Linux / macOS
rm pushed_records.json
```

## AstrBot 定时推送

1. 在 AstrBot 中连接 MCP Server；
2. 新建一个每天 08:00 执行的 FutureTask；
3. 将 [astrbot/system_prompt.md](astrbot/system_prompt.md) 的内容作为系统提示词；
4. 将任务投递到 QQ 私聊或群聊；
5. 先手动执行一次，确认工具调用和消息格式正常。

完整配置说明见 [astrbot/future_task_guide.md](astrbot/future_task_guide.md)。

## 常见问题

### 爬取失败或返回空列表

检查 Chrome 安装、`chrome_path` 配置和目标网址连通性；必要时使用 `--no-head` 观察页面。

### MCP 工具找不到

确认 AstrBot 使用的是安装依赖的 Python，且 MCP 配置中的 `mcp_server.py` 使用绝对路径。

### 每次都返回空列表

可能是通知已经写入 `pushed_records.json`。删除记录文件后重新测试。

## 许可证

本项目使用 MIT License。请合理控制访问频率，并遵守目标网站的使用条款。
