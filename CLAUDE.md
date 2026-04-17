# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Hermes DingTalk 是 Hermes Agent 的**钉钉平台适配器**，支持 Stream Mode 实时消息收发。

## 架构

本项目是标准的 Python 包（`src/` 布局）：

- **`src/hermes_dingtalk/adapter.py`** — 核心适配器，实现 `DingTalkAdapter`
- **`src/hermes_dingtalk/stubs/`** — Hermes Gateway 接口桩，允许独立测试

### 核心设计模式

- **Stream Mode WebSocket** — 通过 `dingtalk-stream` SDK 维持长连接
- **消息去重** — 300 秒窗口，最多 1000 条记录
- **Session Webhook 路由** — 按 `chat_id` 缓存 webhook URL
- **互动卡片** — 消息处理中发"正在处理"卡片，完成后更新为回复
- **指数退避重连** — `[2, 5, 10, 30, 60]` 秒

### 导入优先级

```
gateway.config / gateway.platforms.base  ← Hermes Agent 环境
         ↓（不存在时）
stubs/config / stubs/base               ← 独立运行桩
```

## 依赖安装

```bash
pip install -e .
# 或
pip install dingtalk-stream>=0.23.0 httpx
```

## 已知问题

### `websockets` 版本兼容性

- `dingtalk-stream 0.23.x` 支持 `websockets>=15.x`
- `dingtalk-stream 0.24.x` 在 `websockets 15.x` 下有 `websockets.exceptions` 兼容问题
- 如遇问题，降级到 `pip install dingtalk-stream==0.23.0`

### `await start()` 必须有括号

```python
# 正确
await self._stream_client.start()

# 错误 — 缺失括号
await self._stream_client.start
```

## 与旧版 `dingtalk.py` 的区别

旧版（yueraaaa/hermes-agent）是单文件设计，直接覆盖 `gateway/platforms/dingtalk.py`。

本项目（hermes-dingtalk）是完整包，可通过 `pip install` 安装，不污染 Hermes 源码树。
