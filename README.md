# Hermes DingTalk 通讯模块

修复版的钉钉平台适配器，兼容 `dingtalk-stream>=0.1.0` SDK。

## 修复内容

1. **`CallbackMessage` 属性访问修复** — SDK 传递的是 `CallbackMessage` 对象（数据在 `.data` 字典中），原代码错误地直接访问 snake_case 属性导致全为 `None`
2. **文本提取修复** — 当消息无 `msgtype` 字段时，文本存储在 `msg.extensions['text']` 而非 `msg.text`，原代码漏掉了这个回退路径

## 依赖

```bash
pip install dingtalk-stream httpx
```

## 安装

### 方式一：覆盖现有文件（推荐用于已安装 hermes-agent）

```bash
# 备份原文件
cp gateway/platforms/dingtalk.py gateway/platforms/dingtalk.py.bak

# 覆盖
cp hermes_dingtalk/dingtalk.py gateway/platforms/dingtalk.py

# 重启 gateway
hermes gateway restart
```

### 方式二：独立部署

```bash
export DINGTALK_CLIENT_ID=your-app-key
export DINGTALK_CLIENT_SECRET=your-secret
```

## 配置

在 `~/.hermes/config.yaml` 或项目 `config.yaml` 中：

```yaml
platforms:
  dingtalk:
    enabled: true
    extra:
      client_id: "your-app-key"
      client_secret: "your-secret"
```

或在 `~/.hermes/.env` 中：

```bash
DINGTALK_CLIENT_ID=your-app-key
DINGTALK_CLIENT_SECRET=your-secret
```

## 钉钉开放平台配置

1. 进入 [钉钉开放平台](https://open.dingtalk.com/)
2. 创建企业内部应用 → 机器人
3. 配置消息接收模式为「Stream 模式」
4. 获取 `Client ID` 和 `Client Secret`
5. 将机器人添加到群聊或单聊

## 验证连接

```bash
python -c "
import asyncio, dingtalk_stream
async def test():
    cred = dingtalk_stream.Credential('your-client-id', 'your-client-secret')
    client = dingtalk_stream.DingTalkStreamClient(cred)
    print('SDK OK' if cred else 'FAIL')
asyncio.run(test())
"
```

## 消息类型支持

| 类型 | 状态 |
|------|------|
| 文本消息 | ✅ |
| Markdown 回复 | ✅ |
| 图片/文件/语音 | 回退为 URL 文本 |
| 群聊/单聊 | ✅ |
| Stream Mode 长连接 | ✅ |
| 自动重连 | ✅ |

## 工作原理

```
钉钉服务器 ←WebSocket→ dingtalk-stream SDK ←CallbackMessage→ DingTalkAdapter
                                                              ↓
                                                    Hermes Gateway 处理
                                                              ↓
                                                    session_webhook 回复
```

## 故障排查

**DingTalk 已连接但无法收发消息：**
- 确认机器人已添加到群/单聊
- 首次发送消息后才能获得 session_webhook

**Stream 连接断开/重连：**
- 正常现象，SDK 内置自动重连机制

**模块导入失败：**
- 确认已安装：`pip install dingtalk-stream httpx`
- 确认 hermes-agent 版本支持 dingtalk 平台
