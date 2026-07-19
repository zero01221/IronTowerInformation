"""中国铁塔电子采购平台爬虫

数据来源: https://ebid.chinatowercom.cn/zgtt/gggs/003001/detailpage.html
API接口: /inteligentsearch/rest/esinteligentsearch/getFullTextDataNew

关键发现 (通过逆向 detailpage.js):
- Content-Type 必须是 application/json (不是 form-urlencoded!)
- 参数必须用 JSON.stringify 序列化
- 必须带 isBusiness: "1" 参数
- condition 是数组格式: [{fieldName, equal, isLike, likeType}]
- 响应结构: result.records / result.totalcount
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional
from ..models import BidItem
from ..base_crawler import BaseCrawler
from ..utils import logger


class ChinaTowerComCrawler(BaseCrawler):
    """中国铁塔电子采购平台 (ebid.chinatowercom.cn)"""

    name = "中国铁塔电子采购平台"
    base_url = "https://ebid.chinatowercom.cn"
    detail_page_url = "https://ebid.chinatowercom.cn/zgtt/gggs/003001/detailpage.html"
    api_url = "https://ebid.chinatowercom.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"

    # 分类号
    DEFAULT_CATEGORY = "003001"  # 采购公告

    # 云南行政区划代码前缀（53 = 云南省所有市区）
    # 530000=省级, 530100=昆明, 530300=曲靖, 530400=玉溪, 530500=保山,
    # 530600=昭通, 530700=丽江, 530800=普洱, 530900=临沧, 532300=楚雄,
    # 532500=红河, 532600=文山, 532800=西双版纳, 532900=大理,
    # 533100=德宏, 533300=怒江, 533400=迪庆
    YUNNAN_AREA_CODE = "53"  # 前缀匹配覆盖云南全境

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("chinatowercom", source_config)
        self.keywords = self.config.get("keywords", ["铁塔"])
        if self.config.get("api_url"):
            self.api_url = self.config["api_url"]
        self._category = self.config.get("category", self.DEFAULT_CATEGORY)
        self._page_size = self.config.get("page_size", 30)
        self._max_pages = self.config.get("max_pages", 3)
        # 时间范围：默认7天（近一周）
        self._days_limit = self.config.get("days_limit", 7)
        # 地区过滤：默认限制云南
        self._region_code = self.config.get("region_code", self.YUNNAN_AREA_CODE)
        self._region_enabled = self.config.get("region_filter", True)

    def _get_headers(self) -> dict:
        """构建 API 请求头（完全模拟 detailpage.js 的 AJAX 调用）"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.detail_page_url,
            "Origin": self.base_url,
        }

    def _build_params(self, keyword: str, page_index: int) -> dict:
        """
        构建 API 请求参数 — 完全匹配 detailpage.js 的 getDataInit() 格式

        关键点:
        - cnum 固定为 "001"（分类过滤通过 condition 数组实现）
        - isBusiness 必须为 "1"
        - null 值必须用 Python None（序列化为 JSON null）
        - condition 是对象数组，不是字符串
        - 地区过滤: xiaqucode 前缀匹配（53=云南全境）
        - 时间过滤: time 数组 [{fieldName, startTime, endTime}]
        """
        condition = []
        # 分类条件
        if self._category:
            condition.append({
                "fieldName": "categorynum",
                "equal": self._category,
                "isLike": True,
                "likeType": 2,
            })
        # 地区条件 — 限制云南（xiaqucode 前缀匹配 "53"）
        if self._region_enabled and self._region_code:
            condition.append({
                "fieldName": "xiaqucode",
                "equal": self._region_code,
                "isLike": True,
                "likeType": 2,  # 前缀匹配: "53" 匹配 530000, 530100, 532300 等
            })

        # 时间条件 — 限制最近N天
        time_condition = None
        if self._days_limit > 0:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self._days_limit)
            time_condition = [{
                "fieldName": "infodate",
                "startTime": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "endTime": end_date.strftime("%Y-%m-%d %H:%M:%S"),
            }]

        return {
            "token": "",
            "pn": page_index * self._page_size,
            "rn": self._page_size,
            "sdt": "",
            "edt": "",
            "wd": keyword or "",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "title",
            "cnum": "001",
            "sort": '{"webdate":0}',
            "ssort": "title",
            "cl": 500,
            "terminal": "",
            "condition": condition,
            "time": time_condition,
            "highlights": "title",
            "statistics": None,
            "unionCondition": None,
            "accuracy": "",
            "noParticiple": "",
            "searchRange": None,
            "isBusiness": "1",
        }

    def fetch(self) -> List[BidItem]:
        """获取招标信息"""
        all_items = []

        for keyword in self.keywords:
            logger.info(f"[{self.display_name}] 搜索关键词: {keyword}")
            items = self._fetch_keyword(keyword)
            all_items.extend(items)
            self.delay()

        return all_items

    def _fetch_keyword(self, keyword: str) -> List[BidItem]:
        """获取指定关键词的招标信息"""
        items = []

        for page in range(self._max_pages):
            page_items = self._fetch_page(keyword, page)
            if not page_items:
                break
            items.extend(page_items)

            # 如果返回数少于页大小，说明已是最后一页
            if len(page_items) < self._page_size:
                break

            if page < self._max_pages - 1:
                self.delay(1, 3)

        logger.info(f"  找到 {len(items)} 个结果（共 {self._max_pages} 页）")
        return items

    def _fetch_page(self, keyword: str, page_index: int) -> List[BidItem]:
        """获取单页数据"""
        import requests as req

        params = self._build_params(keyword, page_index)

        try:
            resp = req.post(
                self.api_url,
                json=params,  # ← 关键：用 json= 参数发送 JSON
                headers=self._get_headers(),
                timeout=self.timeout,
                proxies=self.proxies if self.proxies else None,
            )
            resp.raise_for_status()

            data = resp.json()
            records = self._extract_records(data)
            items = []
            for record in records:
                item = self._parse_record(record, keyword)
                if item:
                    items.append(item)
            return items

        except req.exceptions.HTTPError as e:
            logger.warning(f"[{self.display_name}] HTTP错误 {e.response.status_code}: {self.api_url}")
            return []
        except req.exceptions.Timeout:
            logger.warning(f"[{self.display_name}] 请求超时: {self.api_url}")
            return []
        except Exception as e:
            logger.error(f"[{self.display_name}] 请求失败 (关键词: {keyword}, 页: {page_index}): {e}")
            return []

    def _extract_records(self, resp_data: dict) -> list:
        """
        从 API 响应中提取记录列表

        响应结构 (来自 detailpage.js):
        {
            "result": {
                "totalcount": 95707,
                "records": [...]
            }
        }
        注意: result 可能是字符串（需要二次 JSON 解析）
        """
        if not resp_data:
            return []

        result = resp_data.get("result", {})
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.warning(f"[{self.display_name}] result字段JSON解析失败")
                return []

        if isinstance(result, dict):
            return result.get("records", [])
        return []

    def _parse_record(self, record: dict, keyword: str = "") -> Optional[BidItem]:
        """解析单条记录"""
        try:
            # 标题 — 可能包含 HTML 高亮标签 <em>
            title = record.get("title", "") or record.get("TITLE", "")
            if not title:
                return None

            # 去除高亮标签
            import re
            title_clean = re.sub(r'<[^>]+>', '', title).strip()

            # URL — 字段可能为空，需要用 infoid 拼接
            url = record.get("url", "") or record.get("URL", "")
            if not url:
                infoid = record.get("infoid", "") or record.get("INFOID", "")
                if infoid:
                    url = f"https://ebid.chinatowercom.cn/zgtt/gggs/{self._category}/{infoid}.html"

            # 日期
            pub_date = (record.get("infodate", "") or record.get("INFODATE", "") or
                       record.get("webdate", "") or record.get("publishDate", "") or
                       record.get("createTime", ""))

            date_obj = None
            if pub_date:
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                    try:
                        date_obj = datetime.strptime(str(pub_date)[:19], fmt)
                        break
                    except ValueError:
                        continue
            if not date_obj:
                date_obj = datetime.now()

            # 摘要
            description = record.get("content", "") or record.get("CONTENT", "")
            if description:
                description = re.sub(r'<[^>]+>', '', str(description)).strip()

            return BidItem(
                title=title_clean,
                url=url,
                date=date_obj.strftime("%Y-%m-%d"),
                source=self.name,
                description=description[:500] if description else "",
            )
        except Exception as e:
            logger.error(f"[{self.name}] 解析记录失败: {e}")
            return None
