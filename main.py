"""
AstrBot GeoIP 归属地查询插件
==============================
自动检测聊天消息中的 IP 地址（IPv4/IPv6），通过 ip-api.com 和 ip9.com.cn 
双 API 并行查询 IP 归属地，按国别智能区分国内/海外结果并引用回复。

功能特性：
- 自动提取消息中的公网 IP 地址
- 双 API 并行查询，智能融合结果
- 国别判断逻辑：至少一个 API 标记为 CN → 中国 IP
- 中国 IP 显示省/市/区/运营商，海外 IP 显示国家/行政区/城市/运营商
- 引用原始消息回复
- 按 UMO 平台维度启用/禁用自动查询
- WebUI 可视化配置
"""

import re
import asyncio
from typing import Optional, List

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp


@register(
    "astrbot_plugin_geoip",
    "果冻大神",
    "IP 归属地自动查询插件。自动识别消息中的 IP 地址并查询其地理位置。",
    "1.0.0",
)
class GeoIPPlugin(Star):
    """IP 归属地查询插件主类。"""

    # ──────────────────────────────────────────
    # 声明 support_platforms 元数据
    # ──────────────────────────────────────────

    def __init__(self, context: Context):
        super().__init__(context)
        self.http_session: Optional[aiohttp.ClientSession] = None
        # _enabled_platforms: 空列表 = 所有平台均启用；非空 = 仅列表中的平台启用
        self._enabled_platforms: List[str] = []
        # 缓存 _conf_schema.json 中的配置值
        self._plugin_config: dict = {}

    async def initialize(self):
        """异步初始化：创建 HTTP session、加载配置和平台启用状态。"""
        # 创建全局 HTTP session（复用连接）
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "AstrBot-GeoIP-Plugin/1.0"},
        )

        # 加载 _conf_schema.json 配置
        try:
            if hasattr(self.context, "get_config"):
                self._plugin_config = self.context.get_config() or {}
            else:
                self._plugin_config = {}
        except Exception as e:
            logger.debug(f"geoip: 通过 context.get_config() 加载配置失败: {e}")
            self._plugin_config = {}

        # 从 KV 存储加载平台启用状态
        try:
            self._enabled_platforms = await self.get_kv_data("enabled_platforms", [])
            if not isinstance(self._enabled_platforms, list):
                self._enabled_platforms = []
        except Exception as e:
            logger.error(f"geoip: 加载平台启用状态失败: {e}")
            self._enabled_platforms = []

        logger.info(
            f"geoip: 插件初始化完成，已启用平台: "
            f"{'全部' if not self._enabled_platforms else ', '.join(self._enabled_platforms)}"
        )

    async def terminate(self):
        """插件卸载时关闭 HTTP session，释放连接。"""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()

    # ──────────────────────────────────────────
    # 配置读取辅助方法
    # ──────────────────────────────────────────

    def _get_cfg(self, key: str, default):
        """安全读取 _conf_schema.json 中的配置值。"""
        return self._plugin_config.get(key, default)

    # ──────────────────────────────────────────
    # IP 提取模块
    # ──────────────────────────────────────────

    @staticmethod
    def _extract_ip(
        text: str,
        filter_private: bool = True,
        enable_ipv6: bool = True,
    ) -> Optional[str]:
        """
        从文本中提取第一个公网 IP 地址。

        Args:
            text: 输入文本。
            filter_private: 是否过滤私有/保留地址。
            enable_ipv6: 是否识别 IPv6 地址。

        Returns:
            提取到的 IP 字符串，未匹配到则返回 None。
        """
        if not text:
            return None

        # ── IPv4 正则 ──
        ipv4_pattern = (
            r"\b(?:"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
            r"\b"
        )

        # 私有/保留 IPv4 范围列表：(pattern, 描述)
        private_ipv4_patterns = [
            (r"^127\.", "回环"),
            (r"^10\.", "私网 A"),
            (r"^172\.(?:1[6-9]|2\d|3[01])\.", "私网 B"),
            (r"^192\.168\.", "私网 C"),
            (r"^169\.254\.", "链路本地"),
            (r"^0\.", "当前网络"),
            (r"^22[4-9]\.|^23[0-9]\.", "组播"),
            (r"^24[0-9]\.|^25[0-5]\.", "保留"),
        ]

        # ── 匹配 IPv4 ──
        for match in re.finditer(ipv4_pattern, text):
            ip = match.group()
            if filter_private:
                is_private = any(
                    re.match(pattern, ip) for pattern, _ in private_ipv4_patterns
                )
                if not is_private:
                    return ip
            else:
                return ip

        # ── IPv6（如启用）──
        if enable_ipv6:
            # 标准完整 IPv6
            ipv6_full = r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
            # 压缩 IPv6（含 ::）
            ipv6_compressed = (
                r"\b(?:" r"(?:[0-9a-fA-F]{1,4}:){1,7}:" r"|" r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}" r"|"
                r"(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}" r"|"
                r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}" r"|"
                r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}" r"|"
                r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}" r"|"
                r"[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}" r"|"
                r":(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)" r")"
                r"\b"
            )
            # 合并 IPv6 正则
            ipv6_pattern = rf"(?:{ipv6_full}|{ipv6_compressed})"

            for match in re.finditer(ipv6_pattern, text):
                ip = match.group()
                if filter_private:
                    # 过滤 IPv6 特殊地址
                    lower_ip = ip.lower()
                    if any(
                        lower_ip.startswith(prefix)
                        for prefix in ("fe80:", "fc00:", "fd00:", "ff00:", "::1")
                    ):
                        continue
                return ip

        return None

    # ──────────────────────────────────────────
    # API 调用模块
    # ──────────────────────────────────────────

    async def _query_ip_api(self, ip: str, timeout: int = 5) -> Optional[dict]:
        """
        调用 ip-api.com 查询 IP 归属地（适用于全球 IP）。

        Args:
            ip: 待查询的 IP 地址。
            timeout: 超时秒数。

        Returns:
            解析后的 JSON 字典，失败返回 None。
        """
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        try:
            async with self.http_session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"geoip: ip-api 返回非 200 状态码: {resp.status}")
                    return None
                data = await resp.json()
                if data.get("status") == "fail":
                    logger.warning(
                        f"geoip: ip-api 查询失败: {data.get('message', '')}"
                    )
                    return None
                return data
        except asyncio.TimeoutError:
            logger.warning(f"geoip: ip-api 请求超时 (ip={ip})")
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"geoip: ip-api 请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"geoip: ip-api 未知错误: {e}")
            return None

    async def _query_ip9(self, ip: str, timeout: int = 5) -> Optional[dict]:
        """
        调用 ip9.com.cn 查询 IP 归属地（适用于中国 IP）。

        Args:
            ip: 待查询的 IP 地址。
            timeout: 超时秒数。

        Returns:
            ip9 返回的 data 字段内容（dict），失败返回 None。
        """
        url = f"https://ip9.com.cn/get?ip={ip}"
        try:
            async with self.http_session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"geoip: ip9 返回非 200 状态码: {resp.status}")
                    return None
                data = await resp.json()
                # ip9 返回格式: {"code": 0, "data": {...}, "msg": "success"}
                # code == 0 表示成功
                if data.get("code") != 0:
                    logger.warning(f"geoip: ip9 查询失败: code={data.get('code')}")
                    return None
                return data.get("data")
        except asyncio.TimeoutError:
            logger.warning(f"geoip: ip9 请求超时 (ip={ip})")
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"geoip: ip9 请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"geoip: ip9 未知错误: {e}")
            return None

    # ──────────────────────────────────────────
    # 国别判断与结果组装模块
    # ──────────────────────────────────────────

    @staticmethod
    def _classify_and_format(
        ip: str,
        result_ipapi: Optional[dict],
        result_ip9: Optional[dict],
    ) -> str:
        """
        根据两个 API 的结果判断 IP 归属地并组装回复文本。

        国别判断逻辑（依据：用户需求规格）：
        1. 两个 API 均需查询。
        2. 当至少一个 API 判断为中国 IP 时视为中国 IP。
        3. 当至少一个 API 判断为非中国 IP 时视为海外 IP。
        4. 以第一个成功返回结果的 API 为准进行最终判断。

        结果组装规则：
        - 中国 IP：使用 ip9 结果，返回 prov（省）、city（市）、area（区）、isp（运营商）。
        - 海外 IP：使用 ip-api 结果，返回 country（国家）、regionName（行政区）、
          city（城市）、isp（运营商）。
        - 双 API 均失败时返回查询失败提示。

        Args:
            ip: 被查询的 IP 地址。
            result_ipapi: ip-api 的返回结果，失败时为 None。
            result_ip9: ip9 的返回结果，失败时为 None。

        Returns:
            格式化后的回复文本。
        """
        is_cn: Optional[bool] = None  # None=无法判断, True=中国, False=海外
        first_success: Optional[str] = None  # 记录哪个 API 先成功

        # ── 判断 ip-api 结果 ──
        if result_ipapi is not None:
            first_success = "ipapi"
            cc = result_ipapi.get("countryCode") or ""
            if cc == "CN":
                is_cn = True
            elif cc:
                is_cn = False

        # ── 判断 ip9 结果 ──
        if result_ip9 is not None and first_success is None:
            first_success = "ip9"
            cc = (result_ip9.get("country_code") or "").lower()
            if cc == "cn":
                is_cn = True
            elif cc:
                is_cn = False

        # ── 如果 ip-api 先成功，但只有 ip9 有国别信息 ──
        if result_ipapi is not None and result_ip9 is not None and is_cn is None:
            # 两个都成功但没有国别信息，降级处理
            pass

        # ── 如果只有一个成功，用那个的结果 ──
        if is_cn is None:
            if result_ipapi is not None:
                is_cn = False  # 默认非中国
            elif result_ip9 is not None:
                is_cn = True  # 默认中国

        # ── 组装结果 ──
        if is_cn is True and result_ip9 is not None:
            # 中国 IP → ip9 数据
            prov = result_ip9.get("prov") or ""
            city = result_ip9.get("city") or ""
            area = result_ip9.get("area") or ""
            isp = result_ip9.get("isp") or ""
            parts = [p for p in [prov, city, area] if p]
            location = " ".join(parts) if parts else "未知"
            isp_str = isp or "未知"
            return (
                f"🌐 IP 归属地查询结果\n"
                f"IP: {ip}\n"
                f"归属地: {location}\n"
                f"运营商: {isp_str}"
            )

        if is_cn is False and result_ipapi is not None:
            # 海外 IP → ip-api 数据
            country = result_ipapi.get("country") or ""
            region = result_ipapi.get("regionName") or ""
            city = result_ipapi.get("city") or ""
            isp = result_ipapi.get("isp") or ""
            parts = [p for p in [country, region, city] if p]
            location = " ".join(parts) if parts else "未知"
            isp_str = isp or "未知"
            return (
                f"🌐 IP 归属地查询结果\n"
                f"IP: {ip}\n"
                f"归属地: {location}\n"
                f"运营商: {isp_str}"
            )

        # ── 降级：任意一个可用结果 ──
        if result_ipapi is not None:
            country = result_ipapi.get("country") or ""
            region = result_ipapi.get("regionName") or ""
            city = result_ipapi.get("city") or ""
            isp = result_ipapi.get("isp") or ""
            parts = [p for p in [country, region, city] if p]
            location = " ".join(parts) if parts else "未知"
            isp_str = isp or "未知"
            return (
                f"🌐 IP 归属地查询结果\n"
                f"IP: {ip}\n"
                f"归属地: {location}\n"
                f"运营商: {isp_str}"
            )

        if result_ip9 is not None:
            prov = result_ip9.get("prov") or ""
            city = result_ip9.get("city") or ""
            area = result_ip9.get("area") or ""
            isp = result_ip9.get("isp") or ""
            parts = [p for p in [prov, city, area] if p]
            location = " ".join(parts) if parts else "未知"
            isp_str = isp or "未知"
            return (
                f"🌐 IP 归属地查询结果\n"
                f"IP: {ip}\n"
                f"归属地: {location}\n"
                f"运营商: {isp_str}"
            )

        # ── 全部失败 ──
        return (
            f"🌐 IP 归属地查询结果\n"
            f"IP: {ip}\n"
            f"归属地: 查询失败，请稍后重试"
        )

    # ──────────────────────────────────────────
    # 平台启用检查
    # ──────────────────────────────────────────

    async def _is_platform_enabled(self, platform_name: str) -> bool:
        """
        检查指定 UMO 平台是否启用了 GeoIP 自动查询。

        当 _enabled_platforms 为空列表时，所有平台均视为已启用。
        """
        if not self._enabled_platforms:
            return True
        return platform_name.lower() in self._enabled_platforms

    async def _save_enabled_platforms(self):
        """将启用的平台列表持久化到 AstrBot KV 存储。"""
        try:
            await self.put_kv_data("enabled_platforms", self._enabled_platforms)
        except Exception as e:
            logger.error(f"geoip: 保存平台启用状态失败: {e}")

    # ──────────────────────────────────────────
    # 指令组：平台启用/禁用控制
    # ──────────────────────────────────────────

    @filter.command_group("geoip")
    def geoip(self):
        """IP 归属地查询插件管理指令组。"""
        pass

    @geoip.command("enable")
    async def geoip_enable(self, event: AstrMessageEvent, platform: str):
        """
        在指定 UMO 平台上启用 GeoIP 自动查询。

        用法: /geoip enable <platform_name>
        示例: /geoip enable aiocqhttp
        """
        platform = platform.strip().lower()
        if not platform:
            yield event.plain_result("⚠️ 请指定平台名称，例如: /geoip enable aiocqhttp")
            return

        # 当从"全部启用"切换到"部分启用"时给出提示
        was_all_enabled = not self._enabled_platforms

        if platform not in self._enabled_platforms:
            self._enabled_platforms.append(platform)
            await self._save_enabled_platforms()

        msg = f"✅ 已在平台 `{platform}` 启用 GeoIP 自动查询。"
        if was_all_enabled:
            msg += (
                "\n💡 注意：之前为「全部启用」状态，添加后仅列表中的平台会生效。"
                "\n   如需恢复全部启用，请使用 /geoip enable_all"
            )
        yield event.plain_result(msg)

    @geoip.command("disable")
    async def geoip_disable(self, event: AstrMessageEvent, platform: str):
        """
        禁用指定 UMO 平台上的 GeoIP 自动查询。

        用法: /geoip disable <platform_name>
        示例: /geoip disable telegram
        """
        platform = platform.strip().lower()
        if not platform:
            yield event.plain_result("⚠️ 请指定平台名称，例如: /geoip disable aiocqhttp")
            return

        if platform in self._enabled_platforms:
            self._enabled_platforms.remove(platform)
            await self._save_enabled_platforms()
            yield event.plain_result(f"❌ 已在平台 `{platform}` 禁用 GeoIP 自动查询。")
        else:
            if not self._enabled_platforms:
                yield event.plain_result(
                    f"ℹ️ 当前为「全部启用」状态，平台 `{platform}` 不在禁用列表中。\n"
                    f"   如需禁用特定平台，请先使用 /geoip enable_all\n"
                    f"   然后逐个禁用不需要的平台。"
                )
            else:
                yield event.plain_result(
                    f"ℹ️ 平台 `{platform}` 不在已启用列表中。"
                )

    @geoip.command("enable_all")
    async def geoip_enable_all(self, event: AstrMessageEvent):
        """启用所有平台上的 GeoIP 自动查询（清空白名单）。"""
        self._enabled_platforms = []
        await self._save_enabled_platforms()
        yield event.plain_result("✅ 已启用所有平台的 GeoIP 自动查询。")

    @geoip.command("status")
    async def geoip_status(self, event: AstrMessageEvent):
        """查看各 UMO 平台的 GeoIP 启用状态。"""
        lines: list[str] = ["📋 GeoIP 平台启用状态"]

        if not self._enabled_platforms:
            lines.append("▸ 当前模式: 全部启用 🌐")
        else:
            lines.append(
                f"▸ 当前模式: 白名单（{len(self._enabled_platforms)} 个平台）"
            )
            lines.append(f"▸ 已启用: {', '.join(sorted(self._enabled_platforms))}")

        # 尝试枚举所有已加载的平台并标记状态
        try:
            platforms = self.context.platform_manager.get_insts()
            if platforms:
                lines.append("")
                lines.append("可用平台:")
                for p in platforms:
                    pname = (
                        p.__class__.__name__
                        .replace("Adapter", "")
                        .replace("Platform", "")
                        .lower()
                    )
                    enabled = not self._enabled_platforms or pname in self._enabled_platforms
                    status_icon = "✅" if enabled else "❌"
                    lines.append(f"  {status_icon} {pname}")
        except Exception as e:
            logger.debug(f"geoip: 获取平台列表失败: {e}")

        yield event.plain_result("\n".join(lines))

    # ──────────────────────────────────────────
    # 消息监听器：自动提取 IP 并查询归属地
    # ──────────────────────────────────────────

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """
        监听所有消息事件，自动提取 IP 地址并查询归属地。

        处理流程：
        1. 获取消息纯文本
        2. 提取公网 IP（支持 IPv4/IPv6）
        3. 检查当前平台是否启用
        4. 并行查询 ip-api.com 和 ip9.com.cn
        5. 国别判断与结果组装
        6. 引用原始消息回复
        """
        try:
            message_str = event.message_str
            if not message_str:
                return

            # ── 1. 读取配置 ──
            filter_private = self._get_cfg("enable_private_ip_filter", True)
            enable_ipv6 = self._get_cfg("enable_ipv6", True)
            api_timeout = self._get_cfg("api_timeout", 5)
            if not isinstance(api_timeout, (int, float)) or api_timeout < 1:
                api_timeout = 5

            # ── 2. 提取 IP ──
            ip = self._extract_ip(
                message_str,
                filter_private=filter_private,
                enable_ipv6=enable_ipv6,
            )
            if not ip:
                return

            # ── 3. 检查平台是否启用 ──
            platform_name = event.get_platform_name()
            if not await self._is_platform_enabled(platform_name):
                logger.debug(
                    f"geoip: 平台 {platform_name} 未启用，跳过 IP {ip}"
                )
                return

            logger.info(
                f"geoip: 检测到 IP {ip} (平台: {platform_name})"
            )

            # ── 4. 并行查询两个 API ──
            result_ipapi, result_ip9 = await asyncio.gather(
                self._query_ip_api(ip, api_timeout),
                self._query_ip9(ip, api_timeout),
            )

            # ── 5. 组装结果 ──
            reply_text = self._classify_and_format(ip, result_ipapi, result_ip9)

            # ── 6. 检查自定义回复格式 ──
            custom_format = self._get_cfg("reply_format", "")
            if custom_format:
                # 从各个结果中提取字段用于模板替换
                location = "未知"
                isp_str = "未知"
                if result_ip9:
                    prov = result_ip9.get("prov") or ""
                    city = result_ip9.get("city") or ""
                    area = result_ip9.get("area") or ""
                    isp_str = result_ip9.get("isp") or isp_str
                    parts = [p for p in [prov, city, area] if p]
                    location = " ".join(parts) if parts else location
                elif result_ipapi:
                    country = result_ipapi.get("country") or ""
                    region = result_ipapi.get("regionName") or ""
                    city = result_ipapi.get("city") or ""
                    isp_str = result_ipapi.get("isp") or isp_str
                    parts = [p for p in [country, region, city] if p]
                    location = " ".join(parts) if parts else location

                reply_text = custom_format.replace("{ip}", ip)
                reply_text = reply_text.replace("{location}", location)
                reply_text = reply_text.replace("{isp}", isp_str)

            # ── 7. 构造引用回复消息链 ──
            chain = [
                Comp.Reply(id=event.message_obj.message_id),
                Comp.Plain(reply_text),
            ]
            yield event.chain_result(chain)

        except Exception as e:
            logger.error(f"geoip: 处理消息时出错: {e}", exc_info=True)
