# 🔍 astrbot_plugin_geoip

[![Version](https://img.shields.io/badge/version-v1.0.0-blue)](https://github.com/FruitJelliesGD/astrbot_plugin_geoip)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5%204.9.2-orange)](https://github.com/AstrBotDevs/AstrBot)

🌐 **AstrBot IP 归属地自动查询插件** — 自动检测聊天消息中的 IPv4/IPv6 地址，通过 ip-api.com 和 ip9.com.cn 双 API 并行查询归属地，智能区分国内/海外 IP 并以引用方式回复。

---

## ✨ 功能特性

- 🎯 **自动识别**：无需指令，自动提取消息中的公网 IP（IPv4 + IPv6）
- 🔄 **双 API 融合**：ip-api.com（全球）+ ip9.com.cn（国内），取两者之长
- 🏳️ **国别区分**：自动判断中国/海外 IP，展示不同维度的地理信息
- 💬 **引用回复**：回复自动引用原始消息，上下文清晰
- 🎛️ **平台控制**：按 UMO 消息平台维度启用/禁用
- ⚙️ **WebUI 配置**：所有配置项可在 AstrBot WebUI 中可视化编辑
- 🛡️ **异常安全**：超时处理 + 降级策略，单 API 故障不影响整体运行

---

## 📦 安装

> 要求：AstrBot ≥ 4.9.2，Python ≥ 3.10

### 手动安装

```bash
cd AstrBot/data/plugins/
git clone https://github.com/FruitJelliesGD/astrbot_plugin_geoip.git
```

重启 AstrBot 或在 WebUI 插件管理页点击「重载插件」。

---

## 📖 使用示例

### 自动查询

只需在聊天中发送包含 IP 的消息，机器人自动回复归属地：

```
👤 用户：帮我查一下 8.8.8.8
🤖 机器人：[引用原消息]
🌐 IP 归属地查询结果
IP: 8.8.8.8
归属地: 美国 弗吉尼亚州 阿什本
运营商: Google LLC

👤 用户：114.114.114.114 的服务器在哪？
🤖 机器人：[引用原消息]
🌐 IP 归属地查询结果
IP: 114.114.114.114
归属地: 江苏 南京
运营商: 114DNS
```

### 平台管理指令

| 指令 | 说明 |
|------|------|
| `/geoip enable <平台>` | 在指定平台启用自动查询 |
| `/geoip disable <平台>` | 禁用指定平台 |
| `/geoip enable_all` | 启用所有平台 |
| `/geoip status` | 查看当前各平台状态 |

---

## ⚙️ WebUI 配置项

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `enable_private_ip_filter` | bool | ✅ | 自动过滤 127.x、192.168.x 等私有地址 |
| `api_timeout` | int | `5` | 单个 API 超时（秒） |
| `enable_ipv6` | bool | ✅ | 是否识别 IPv6 地址 |
| `reply_format` | text | 空 | 自定义回复模板（`{ip}` `{location}` `{isp}`） |

---

## 🔧 技术架构

```
消息 → IP 提取(正则) → 平台检查 → 双 API 并行 → 国别判断 → 结果组装 → 引用回复
                          ↓
                    KV 存储(白名单)
```

- **IP 提取**：正则匹配 IPv4/IPv6 + 私有地址过滤
- **API 调用**：`asyncio.gather()` 并行请求 ip-api + ip9
- **国别判断**：至少一个 API 标记为 CN → 中国 IP
- **数据源**：中国 IP 用 ip9（省/市/区），海外 IP 用 ip-api（国家/行政区/城市）

---

## 🐛 故障排查

### 插件加载失败
- 确认 AstrBot ≥ 4.9.2
- 检查 `requirements.txt` 中的依赖是否已安装：`pip install aiohttp`

### 查询无回复
- 确认当前平台已启用（使用 `/geoip status` 查看）
- 确认 IP 是公网地址（私有 IP 默认被过滤）
- 查看 AstrBot 日志确认 API 调用是否超时

### API 查询失败
- 检查服务器能否访问 `ip-api.com` 和 `ip9.com.cn`
- 在 WebUI 中适当增加 `api_timeout` 值

---

## 📄 许可证

MIT License © 2026 果冻大神
