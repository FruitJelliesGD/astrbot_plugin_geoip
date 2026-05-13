# astrbot_plugin_geoip

🌐 **AstrBot IP 归属地自动查询插件**

自动检测聊天消息中的 IP 地址（IPv4/IPv6），通过 **ip-api.com** 和 **ip9.com.cn** 双 API 并行查询归属地，智能区分国内/海外 IP 并以引用方式回复。

## 功能特性

- ✅ **自动识别**：自动提取消息中的公网 IP 地址（IPv4 + IPv6）
- ✅ **双 API 融合**：同时查询 ip-api.com（全球）和 ip9.com.cn（国内），智能合并结果
- ✅ **国别智能判断**：中国 IP 显示省/市/区/运营商，海外 IP 显示国家/行政区/城市/运营商
- ✅ **引用回复**：回复时引用原始消息，清晰关联上下文
- ✅ **平台控制**：通过指令按 UMO 消息平台维度和模块启用/禁用
- ✅ **WebUI 配置**：通过 AstrBot WebUI 可视化编辑配置项
- ✅ **异常安全**：完善的超时处理、降级策略，插件不会因单个 API 故障而崩溃

## 安装

### 方式一：通过 AstrBot 插件市场安装

> 待发布

### 方式二：手动安装

将插件克隆到 AstrBot 的 `data/plugins/` 目录下：

```bash
cd AstrBot/data/plugins/
git clone https://github.com/FruitJelliesGD/astrbot_plugin_geoip.git
```

然后重启 AstrBot 或在 WebUI 中重载插件。

## 使用方法

### 自动查询

在任何受支持的聊天平台发送包含公网 IP 地址的消息，机器人会自动查询并回复归属地。

```
用户: 帮我查一下 8.8.8.8
机器人: [引用消息]
🌐 IP 归属地查询结果
IP: 8.8.8.8
归属地: 美国 加利福尼亚州 洛杉矶
运营商: Google LLC

用户: 我的服务器 114.114.114.114 怎么 ping 不通？
机器人: [引用消息]
🌐 IP 归属地查询结果
IP: 114.114.114.114
归属地: 江苏省 南京市
运营商: 南京信风网络科技有限公司
```

### 平台管理指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `/geoip enable <platform>` | 在指定平台启用自动查询 | `/geoip enable aiocqhttp` |
| `/geoip disable <platform>` | 禁用指定平台的自动查询 | `/geoip disable telegram` |
| `/geoip enable_all` | 启用所有平台 | `/geoip enable_all` |
| `/geoip status` | 查看各平台启用状态 | `/geoip status` |

## 配置项

通过 WebUI 插件管理页面可配置以下项：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_private_ip_filter` | bool | `true` | 过滤私有/保留 IP（如 192.168.x.x） |
| `api_timeout` | int | `5` | 单个 API 调用的超时时间（秒） |
| `enable_ipv6` | bool | `true` | 启用 IPv6 地址识别 |
| `reply_format` | text | `""` | 自定义回复模板，支持 `{ip}` `{location}` `{isp}` |

## 依赖

- Python ≥ 3.10
- aiohttp ≥ 3.9.0

## 开发计划

参见 [开发计划文档](https://github.com/FruitJelliesGD/astrbot_plugin_geoip)（待补充）

## 许可证

MIT License
