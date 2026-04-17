# Hermes DingTalk 通讯模块

支持 Stream Mode 的 Hermes Agent 钉钉平台适配器。

## 功能特性

- ✅ **Stream Mode 长连接** — 实时接收消息，无需 Webhook
- ✅ **Markdown 回复** — 支持富文本格式
- ✅ **自动重连** — 指数退避重连（2s→5s→10s→30s→60s）
- ✅ **消息去重** — 300 秒窗口，最高 1000 条记录
- ✅ **互动卡片**（可选）— 消息处理中显示"正在处理..."卡片，完成后更新为回复内容

---

## 升级指南（已有旧版 hermes-dingtalk）

如果你已安装旧版（之前用单文件 `dingtalk.py` 或旧版 pip 包），按以下步骤升级：

### 第一步：升级 dingtalk-stream SDK（如需要）

```bash
# 确认当前版本
pip show dingtalk-stream

# 如果是 0.24.x，降级到 0.23.0
pip install dingtalk-stream==0.23.0
```

### 第二步：替换适配器文件

```bash
# 方式 A：直接复制（简单快速）
cp src/hermes_dingtalk/adapter.py \
  ~/.hermes/hermes-agent/venv/lib/python3.11/site-packages/hermes_dingtalk/adapter.py

# 方式 B：卸载旧包 + pip 安装新包
pip uninstall hermes-dingtalk -y
pip install hermes-dingtalk
```

### 第三步：重启 Gateway

```bash
# 方式 A：使用 hermes 命令
hermes gateway restart

# 方式 B：手动重启
pkill -f "hermes.*gateway"
cd ~/.hermes/hermes-agent && nohup venv/bin/python -m hermes_cli.main gateway run --replace &
```

### 验证是否生效

```bash
# 查看 Gateway 日志，确认无 Stream error
tail -f ~/.hermes/logs/gateway.log
```

---

## 首次安装

```bash
# 安装依赖
pip install dingtalk-stream==0.23.0 httpx

# 复制适配器
cp src/hermes_dingtalk/adapter.py \
  ~/.hermes/hermes-agent/venv/lib/python3.11/site-packages/hermes_dingtalk/adapter.py

# 重启 Gateway
hermes gateway restart
```

---

## 配置

在 `~/.hermes/config.yaml` 中：

```yaml
platforms:
  dingtalk:
    enabled: true
    extra:
      client_id: "your-app-key"
      client_secret: "your-secret"
      card_template_id: "..."      # 可选：互动卡片模板 ID
```

或在 `~/.hermes/.env` 中：

```bash
DINGTALK_CLIENT_ID=your-app-key
DINGTALK_CLIENT_SECRET=***
```

---

## 钉钉开放平台配置

1. 进入 [钉钉开放平台](https://open.dingtalk.com/)
2. 创建企业内部应用 → 机器人
3. 配置消息接收模式为「Stream 模式」
4. 获取 `Client ID` 和 `Client Secret`
5. 将机器人添加到群聊或单聊

---

## 互动卡片（可选）

要启用"正在处理..."卡片功能，需要：

1. 在[钉钉开放平台](https://open.dingtalk.com/)创建互动卡片模板
2. 模板需包含 `title` 和 `content` 参数
3. 在 `config.yaml` 中配置 `card_template_id`

不配置卡片模板 ID 时，系统会降级为普通 markdown 消息，不影响正常通讯。

---

## 修复历史

### v0.2.0（2026-04-17）

- `dingtalk-stream>=0.23.0` 兼容 `websockets>=15.x`
- `await start()` 协程调用方式修复
- Processing Card 互动卡片功能
- 从单文件改为完整 pip 包结构

### v1.0.0（更早版本）

- 基础 Stream Mode 支持
- 消息去重
- 自动重连

---

## 目录结构

```
hermes_dingtalk/
├── src/hermes_dingtalk/
│   ├── __init__.py          # 包入口
│   ├── adapter.py           # 核心适配器
│   └── stubs/               # Hermes gateway 接口桩（独立运行用）
│       ├── __init__.py
│       ├── base.py
│       ├── config.py
│       ├── helpers.py
│       └── session.py
├── pyproject.toml
├── requirements.txt
├── README.md
└── LICENSE
```
