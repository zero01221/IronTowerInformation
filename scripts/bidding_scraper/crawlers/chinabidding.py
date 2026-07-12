# coding=utf-8
"""中国采购与招标网爬虫 - 使用 Selenium 绕过 Cloudflare"""

from typing import List, Optional
import time

from bs4 import BeautifulSoup

from ..base_crawler import BaseCrawler
from ..logger import get_logger
from ..models import BidItem
from ..utils import extract_date, clean_text

logger = get_logger(__name__)


class ChinabiddingCrawler(BaseCrawler):
    """中国采购与招标网爬虫 - 使用 Selenium"""
    
    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("chinabidding", source_config)
        self.search_url = self.config.get("search_url", "https://www.chinabidding.com/search/proj.htm")
        self.keyword = self.config.get("keyword", "铁塔")
        self.max_pages = self.config.get("max_pages", 1)
        self.driver = None
    
    def _init_driver(self):
        """初始化 Selenium WebDriver"""
        if self.driver:
            return self.driver
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            # 配置 Chrome 选项
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # 无头模式
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 禁用自动化标志
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 初始化 WebDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 执行 CDP 命令隐藏 webdriver 标志
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            })
            
            logger.info("  Selenium WebDriver 初始化成功")
            return self.driver
        
        except Exception as e:
            logger.error(f"  Selenium WebDriver 初始化失败: {e}")
            return None
    
    def _close_driver(self):
        """关闭 WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def fetch(self) -> List[BidItem]:
        """抓取招标信息"""
        all_items = []
        
        logger.info(f"[{self.display_name}] 开始抓取: {self.search_url}")
        
        # 初始化 WebDriver
        driver = self._init_driver()
        if not driver:
            logger.error(f"[{self.display_name}] 无法初始化 WebDriver")
            return []
        
        try:
            for page in range(1, self.max_pages + 1):
                items = self._fetch_page(driver, page)
                if not items:
                    break
                all_items.extend(items)
                self.delay()
            
            logger.info(f"  找到 {len(all_items)} 个原始条目")
            
            # 过滤云南地区
            filtered_items = self.filter_by_region(all_items)
            logger.info(f"  过滤后保留 {len(filtered_items)} 条招标信息")
            
            return filtered_items
        
        finally:
            self._close_driver()
    
    def _fetch_page(self, driver, page: int) -> List[BidItem]:
        """获取单页数据 - 使用 Selenium"""
        try:
            # 访问搜索页面
            driver.get(self.search_url)
            
            # 等待页面加载（包括 Cloudflare 验证）
            logger.info(f"  等待页面加载...")
            time.sleep(8)
            
            # 查找可见的搜索框 - 使用 CSS 选择器
            from selenium.webdriver.common.by import By
            search_inputs = driver.find_elements(By.CSS_SELECTOR, "input#fullText[type='text']")
            logger.info(f"  找到 {len(search_inputs)} 个搜索框")
            
            search_input = None
            for inp in search_inputs:
                if inp.is_displayed() and inp.is_enabled():
                    search_input = inp
                    break
            
            if not search_input:
                # 尝试备用方法：查找所有 input 元素
                all_inputs = driver.find_elements(By.TAG_NAME, "input")
                logger.info(f"  备用方法: 找到 {len(all_inputs)} 个 input 元素")
                for inp in all_inputs:
                    name = inp.get_attribute("name")
                    if name == "fullText" and inp.is_displayed() and inp.is_enabled():
                        search_input = inp
                        break
            
            if not search_input:
                logger.error("  找不到可见的搜索框")
                return []
            
            logger.info("  页面加载完成，开始搜索...")
            search_input.clear()
            search_input.send_keys(self.keyword)
            
            # 选择招标类型（如果有）
            try:
                from selenium.webdriver.support.ui import Select
                po_class_select = driver.find_element(By.NAME, "poClass")
                select = Select(po_class_select)
                select.select_by_value("BidNotice")
            except:
                pass
            
            # 提交搜索
            search_input.submit()
            
            # 等待搜索结果加载
            time.sleep(5)
            
            # 获取页面源码
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            
            return self._parse_page(soup)
        
        except Exception as e:
            logger.error(f"[{self.display_name}] 获取页面失败: {e}")
            return []
    
    def _parse_page(self, soup: BeautifulSoup) -> List[BidItem]:
        """解析页面"""
        items = []
        
        # 查找搜索结果列表
        result_list = soup.select_one("ul.as-pager-body")
        if not result_list:
            # 尝试其他选择器
            result_list = soup.select_one("ul.search-result-list")
            if not result_list:
                return items
        
        for item in result_list.select("li"):
            bid_item = self._parse_item(item)
            if bid_item:
                items.append(bid_item)
        
        return items
    
    def _parse_item(self, item) -> Optional[BidItem]:
        """解析单个条目"""
        try:
            # 标题和链接
            title_el = item.select_one("h5 span.txt")
            if not title_el:
                title_el = item.select_one("h5 a")
            if not title_el:
                return None
            
            title = title_el.get_text(strip=True)
            
            a_tag = item.select_one('a[href*="/project/"]')
            if not a_tag:
                a_tag = item.select_one('a[href]')
            if not a_tag:
                return None
            
            link = a_tag.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.chinabidding.com" + link
            
            # 摘要
            desc_el = item.select_one("p.txt")
            description = desc_el.get_text(strip=True) if desc_el else ""
            
            # 日期
            date_el = item.select_one("span.date") or item.select_one("span.time")
            date_str = date_el.get_text(strip=True) if date_el else ""
            date = extract_date(date_str) if date_str else ""
            
            # 地区
            area_el = item.select_one("span.area")
            area = area_el.get_text(strip=True) if area_el else ""
            if area:
                description = f"{description} 地区：{area}"
            
            return BidItem(
                title=clean_text(title),
                link=link,
                description=clean_text(description),
                date=date,
                source=self.source_name,
            )
        
        except Exception as e:
            logger.debug(f"  解析条目失败: {e}")
            return None
