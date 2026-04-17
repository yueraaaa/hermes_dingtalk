# Hermes DingTalk 通讯模块

支持 Stream Mode 的 Hermes Agent 钉钉平台适配器。

## 功能特性

- ✅ **Stream Mode 长连接** — 实时接收消息，无需 Webhook
- ✅ **Markdown 回复** — 支持富文本格式
- ✅ **自动重连** — 指数退避重连（2s→5s→10s→30s→60s）
- ✅ **消息去重** — 300 秒窗口，最高 1000 条记录
- ✅ **互动卡片**（可选）— 消息处理中显示"正在处理..."卡片，完成后更新为回复内容

## 修复内容（v0.2.0）

本次更新（2026-04-17）修复了以下问题：

1. **`websockets` 版本兼容** — `dingtalk-stream>=0.23.0` 兼容 `websockets>=15.x`
2. **`await start()` 调用修复** — 直接 `await self._stream_client.start()`，不再使用 `asyncio.to_thread`
3. **`CallbackMessage` 属性访问** — 数据在 `.data` 字典中，正确处理蛇形属性
4. **文本提取兜底** — 支持 `rich_text` 降级路径
5. **互动卡片功能** — 新增 Processing Card 支持（需配置 `card_template_id`）

## 依赖

```bash
pip install hermes-dingtalk
# 或
pip install dingtalk-stream>=0.23.0 httpx
```

## 安装

### 方式一：作为 pip 包安装（推荐）

```bash
pip install hermes-dingtalk
```

### 方式二：覆盖 hermes-agent 中的旧版文件

如果你的 hermes-agent 使用旧版钉钉适配器：

```bash
# 备份原文件
cp gateway/platforms/dingtalk.py gateway/platforms/dingtalk.py.bak

# 覆盖为新版
cp hermes_dingtalk/dingtalk.py gateway/platforms/dingtalk.py

# 重启 Gateway
hermes gateway restart
```

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

## 钉钉开放平台配置

1. 进入 [钉钉开放平台](https://open.dingtalk.com/)
2. 创建企业内部应用 → 机器人
3. 配置消息接收模式为「Stream 模式」
4. 获取 `Client ID` 和 `Client Secret`
5. 将机器人添加到群聊或单聊

## 互动卡片（可选）

要启用"正在处理..."卡片功能，需要：

1. 在[钉钉开放平台](https://open.dingtalk.com/)创建互动卡片模板
2. 模板需包含 `title` 和 `content` 参数
3. 在 `config.yaml` 中配置 `card_template_id`

不配置卡片模板 ID 时，系统会降级为普通 markdown 消息，不影响正常通讯。

## 消息类型支持

| 类型 | 状态 |
|------|------|
| 文本消息 | ✅ |
| Markdown 回复 | ✅ |
| 图片/文件/语音 | 降级为 URL 文本 |
| 群聊/单聊 | ✅ |
| Stream Mode 长连接 | ✅ |
| 自动重连（含指数退避） | ✅ |
| 互动处理卡片 | ✅（可选）|

## 工作原理

```
钉钉服务器 ←WebSocket→ DingTalkAdapter
                              ↓
                    dingtalk-stream SDK
                              ↓
                    消息 → ChatbotHandler → Hermes Gateway
                              ↓
                    session_webhook 回复
```

## 故障排查

**DingTalk 已连接但无法收发消息：**
- 确认机器人已添加到群/单聊
- 首次发送消息后才能获得 session_webhook

**Stream 连接断开/重连：**
- 正常现象，适配器会自动以指数退避重连

**模块导入失败：**
- 确认已安装：`pip install dingtalk-stream httpx`
- 确认 hermes-agent 版本支持 dingtalk 平台

## 目录结构

```
hermes_dingtalk/
├── src/hermes_dingtalk/
│   ├── __init__.py          # 包入口
│   ├── adapter.py           # 核心适配器（与 venv 中版本一致）
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
