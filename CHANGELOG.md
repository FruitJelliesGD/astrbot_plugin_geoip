# Changelog

所有关于 `astrbot_plugin_geoip` 的显著变更都将记录在此文件。

## [v1.0.0] - 2026-05-14

### 新增功能
- 自动提取消息中的公网 IP 地址（IPv4 + IPv6）
- 双 API 并行查询：ip-api.com + ip9.com.cn
- 国别智能判断：中国 IP 显示省/市/区/运营商，海外 IP 显示国家/行政区/城市/运营商
- 引用原始消息回复
- `/geoip` 指令组：enable / disable / enable_all / status
- WebUI 可视化配置（`_conf_schema.json`）
- 平台维度启用/禁用控制
- 私有/保留 IP 地址过滤
- 自定义回复模板支持
- API 超时降级策略
