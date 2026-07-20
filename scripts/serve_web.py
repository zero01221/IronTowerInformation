#!/usr/bin/env python
# coding=utf-8
"""
铁塔招标信息 Web 前端

用法:
    python scripts/serve_web.py
    浏览器打开 http://localhost:8080

功能:
    - 展示最近 7 天全国铁塔招标信息
    - 支持标题关键字搜索、公告类型筛选、省份筛选
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "output" / "bidding_history.db"
PORT = 8080

# ---------------------------------------------------------------------------
# 地区映射
# ---------------------------------------------------------------------------

# 省份/直辖市/自治区
PROVINCES = [
    "北京", "上海", "天津", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "广西", "海南",
    "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆",
    "内蒙古",
]

# 地州市 → 省份映射（覆盖全国主要地级市/自治州）
CITY_TO_PROVINCE = {
    # === 河北 ===
    "石家庄": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北", "邢台": "河北",
    "保定": "河北", "张家口": "河北", "承德": "河北", "沧州": "河北", "廊坊": "河北", "衡水": "河北",
    # === 山西 ===
    "太原": "山西", "大同": "山西", "阳泉": "山西", "长治": "山西", "晋城": "山西",
    "朔州": "山西", "晋中": "山西", "运城": "山西", "忻州": "山西", "临汾": "山西", "吕梁": "山西",
    # === 内蒙古 ===
    "呼和浩特": "内蒙古", "包头": "内蒙古", "乌海": "内蒙古", "赤峰": "内蒙古", "通辽": "内蒙古",
    "鄂尔多斯": "内蒙古", "呼伦贝尔": "内蒙古", "巴彦淖尔": "内蒙古", "乌兰察布": "内蒙古",
    "兴安": "内蒙古", "锡林郭勒": "内蒙古", "阿拉善": "内蒙古",
    # === 辽宁 ===
    "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "抚顺": "辽宁", "本溪": "辽宁",
    "丹东": "辽宁", "锦州": "辽宁", "营口": "辽宁", "阜新": "辽宁", "辽阳": "辽宁",
    "盘锦": "辽宁", "铁岭": "辽宁", "葫芦岛": "辽宁",
    # === 吉林 ===
    "长春": "吉林", "吉林市": "吉林", "四平": "吉林", "辽源": "吉林", "通化": "吉林",
    "白山": "吉林", "松原": "吉林", "白城": "吉林", "延边": "吉林",
    # === 黑龙江 ===
    "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "鸡西": "黑龙江", "鹤岗": "黑龙江", "双鸭山": "黑龙江",
    "大庆": "黑龙江", "伊春": "黑龙江", "佳木斯": "黑龙江", "七台河": "黑龙江", "牡丹江": "黑龙江",
    "黑河": "黑龙江", "绥化": "黑龙江", "大兴安岭": "黑龙江",
    # === 江苏 ===
    "南京": "江苏", "无锡": "江苏", "徐州": "江苏", "常州": "江苏", "苏州": "江苏",
    "南通": "江苏", "连云港": "江苏", "淮安": "江苏", "盐城": "江苏", "扬州": "江苏",
    "镇江": "江苏", "泰州": "江苏", "宿迁": "江苏",
    # === 浙江 ===
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江", "湖州": "浙江",
    "绍兴": "浙江", "金华": "浙江", "衢州": "浙江", "舟山": "浙江", "台州": "浙江", "丽水": "浙江",
    # === 安徽 ===
    "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "淮南": "安徽", "马鞍山": "安徽",
    "淮北": "安徽", "铜陵": "安徽", "安庆": "安徽", "黄山": "安徽", "滁州": "安徽",
    "阜阳": "安徽", "宿州": "安徽", "六安": "安徽", "亳州": "安徽", "池州": "安徽", "宣城": "安徽",
    # === 福建 ===
    "福州": "福建", "厦门": "福建", "莆田": "福建", "三明": "福建", "泉州": "福建",
    "漳州": "福建", "南平": "福建", "龙岩": "福建", "宁德": "福建",
    # === 江西 ===
    "南昌": "江西", "景德镇": "江西", "萍乡": "江西", "九江": "江西", "新余": "江西",
    "鹰潭": "江西", "赣州": "江西", "吉安": "江西", "宜春": "江西", "抚州": "江西", "上饶": "江西",
    # === 山东 ===
    "济南": "山东", "青岛": "山东", "淄博": "山东", "枣庄": "山东", "东营": "山东",
    "烟台": "山东", "潍坊": "山东", "济宁": "山东", "泰安": "山东", "威海": "山东",
    "日照": "山东", "临沂": "山东", "德州": "山东", "聊城": "山东", "滨州": "山东", "菏泽": "山东",
    # === 河南 ===
    "郑州": "河南", "开封": "河南", "洛阳": "河南", "平顶山": "河南", "安阳": "河南",
    "鹤壁": "河南", "新乡": "河南", "焦作": "河南", "濮阳": "河南", "许昌": "河南",
    "漯河": "河南", "三门峡": "河南", "南阳": "河南", "商丘": "河南", "信阳": "河南",
    "周口": "河南", "驻马店": "河南", "济源": "河南",
    # === 湖北 ===
    "武汉": "湖北", "黄石": "湖北", "十堰": "湖北", "宜昌": "湖北", "襄阳": "湖北",
    "鄂州": "湖北", "荆门": "湖北", "孝感": "湖北", "荆州": "湖北", "黄冈": "湖北",
    "咸宁": "湖北", "随州": "湖北", "恩施": "湖北", "仙桃": "湖北", "潜江": "湖北",
    "天门": "湖北", "神农架": "湖北",
    # === 湖南 ===
    "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "衡阳": "湖南", "邵阳": "湖南",
    "岳阳": "湖南", "常德": "湖南", "张家界": "湖南", "益阳": "湖南", "郴州": "湖南",
    "永州": "湖南", "怀化": "湖南", "娄底": "湖南", "湘西": "湖南",
    # === 广东 ===
    "广州": "广东", "韶关": "广东", "深圳": "广东", "珠海": "广东", "汕头": "广东",
    "佛山": "广东", "江门": "广东", "湛江": "广东", "茂名": "广东", "肇庆": "广东",
    "惠州": "广东", "梅州": "广东", "汕尾": "广东", "河源": "广东", "阳江": "广东",
    "清远": "广东", "东莞": "广东", "中山": "广东", "潮州": "广东", "揭阳": "广东", "云浮": "广东",
    # === 广西 ===
    "南宁": "广西", "柳州": "广西", "桂林": "广西", "梧州": "广西", "北海": "广西",
    "防城港": "广西", "钦州": "广西", "贵港": "广西", "玉林": "广西", "百色": "广西",
    "贺州": "广西", "河池": "广西", "来宾": "广西", "崇左": "广西",
    # === 海南 ===
    "海口": "海南", "三亚": "海南", "三沙": "海南", "儋州": "海南",
    # === 四川 ===
    "成都": "四川", "自贡": "四川", "攀枝花": "四川", "泸州": "四川", "德阳": "四川",
    "绵阳": "四川", "广元": "四川", "遂宁": "四川", "内江": "四川", "乐山": "四川",
    "南充": "四川", "眉山": "四川", "宜宾": "四川", "广安": "四川", "达州": "四川",
    "雅安": "四川", "巴中": "四川", "资阳": "四川", "阿坝": "四川", "甘孜": "四川", "凉山": "四川",
    # === 贵州 ===
    "贵阳": "贵州", "六盘水": "贵州", "遵义": "贵州", "安顺": "贵州", "毕节": "贵州",
    "铜仁": "贵州", "黔西南": "贵州", "黔东南": "贵州", "黔南": "贵州",
    # === 云南 ===
    "昆明": "云南", "曲靖": "云南", "玉溪": "云南", "保山": "云南", "昭通": "云南",
    "丽江": "云南", "普洱": "云南", "临沧": "云南", "楚雄": "云南", "红河": "云南",
    "文山": "云南", "西双版纳": "云南", "大理": "云南", "德宏": "云南", "怒江": "云南", "迪庆": "云南",
    # === 西藏 ===
    "拉萨": "西藏", "日喀则": "西藏", "昌都": "西藏", "林芝": "西藏", "山南": "西藏",
    "那曲": "西藏", "阿里": "西藏",
    # === 陕西 ===
    "西安": "陕西", "铜川": "陕西", "宝鸡": "陕西", "咸阳": "陕西", "渭南": "陕西",
    "延安": "陕西", "汉中": "陕西", "榆林": "陕西", "安康": "陕西", "商洛": "陕西",
    # === 甘肃 ===
    "兰州": "甘肃", "嘉峪关": "甘肃", "金昌": "甘肃", "白银": "甘肃", "天水": "甘肃",
    "武威": "甘肃", "张掖": "甘肃", "平凉": "甘肃", "酒泉": "甘肃", "庆阳": "甘肃",
    "定西": "甘肃", "陇南": "甘肃", "临夏": "甘肃", "甘南": "甘肃",
    # === 青海 ===
    "西宁": "青海", "海东": "青海", "海北": "青海", "黄南": "青海", "果洛": "青海",
    "玉树": "青海", "海西": "青海",
    # === 宁夏 ===
    "银川": "宁夏", "石嘴山": "宁夏", "吴忠": "宁夏", "固原": "宁夏", "中卫": "宁夏",
    # === 新疆 ===
    "乌鲁木齐": "新疆", "克拉玛依": "新疆", "吐鲁番": "新疆", "哈密": "新疆",
    "昌吉": "新疆", "博尔塔拉": "新疆", "巴音郭楞": "新疆", "阿克苏": "新疆",
    "克孜勒苏": "新疆", "喀什": "新疆", "和田": "新疆", "伊犁": "新疆",
    "塔城": "新疆", "阿勒泰": "新疆", "石河子": "新疆",
}

# 所有地区关键词 = 省份 + 地州市（用于在文本中搜索）
ALL_REGION_KEYWORDS = PROVINCES + list(CITY_TO_PROVINCE.keys())


def extract_regions(title: str, description: str = "") -> list:
    """从标题和描述中提取所有地区（省份 + 地州市）

    策略：标题优先。招标项目的归属地由标题决定，正文中可能出现其他省份的
    公司名称（如中标方、代理机构等），不应作为项目归属的依据。
    只有标题中完全找不到地区信息时，才回退到正文中查找。

    返回值会自动补齐：如果找到地州市，会同时加入对应的省份，
    保证前端按省份筛选和标签显示都正确。
    """
    # 先从标题提取
    regions = set(_find_regions(title))
    if not regions:
        # 标题中找不到地区时，才从正文中提取
        regions = set(_find_regions(description))

    # 将地州市映射到对应省份，补齐省份标签
    for r in list(regions):
        province = CITY_TO_PROVINCE.get(r)
        if province:
            regions.add(province)

    return sorted(regions)


def _find_regions(text: str) -> list:
    """在给定文本中查找所有匹配的地区关键词"""
    if not text:
        return []
    return sorted(set(k for k in ALL_REGION_KEYWORDS if k in text))


def extract_bid_type(description: str, source: str = "") -> str:
    """从描述或来源推断公告类型"""
    m = re.search(r'\[(招标公告|开标记录|评标公示|中标公告|采购公告)\]', description)
    if m:
        return m.group(1)
    if "铁塔电子采购" in source:
        return "采购公告"
    if "乙方宝" in source:
        return "招标公告"
    return ""


# ---------------------------------------------------------------------------
# 数据查询
# ---------------------------------------------------------------------------

def get_items(days: int = 7) -> list:
    """从 SQLite 读取最近 N 天的数据"""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """
        SELECT item_id, title, url, date, source, description
        FROM bid_items
        WHERE date >= ?
        ORDER BY date DESC, created_at DESC
        LIMIT 500
        """,
        (cutoff,)
    ).fetchall()

    items = []
    for r in rows:
        desc = r["description"] or ""
        items.append({
            "id": r["item_id"],
            "title": r["title"],
            "url": r["url"],
            "date": r["date"],
            "source": r["source"],
            "description": desc,
            "bidType": extract_bid_type(desc, r["source"]),
            "regions": extract_regions(r["title"], desc),
        })

    conn.close()
    return items


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>铁塔招标信息</title>
<style>
  :root {
    --bg: #f5f6fa; --card: #fff; --text: #2d3436; --muted: #636e72;
    --border: #dfe6e9; --accent: #0984e3; --shadow: 0 2px 8px rgba(0,0,0,.06);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
  .container { max-width: 960px; margin: 0 auto; padding: 16px; }

  .header { background: linear-gradient(135deg, #0984e3, #6c5ce7); color: #fff; padding: 24px 20px; border-radius: 12px; margin-bottom: 20px; }
  .header h1 { font-size: 22px; margin-bottom: 4px; }
  .header .sub { font-size: 13px; opacity: .85; }

  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: var(--card); border-radius: 10px; padding: 14px 20px; flex: 1; min-width: 130px; box-shadow: var(--shadow); text-align: center; }
  .stat .num { font-size: 28px; font-weight: 700; color: var(--accent); }
  .stat .label { font-size: 12px; color: var(--muted); margin-top: 2px; }

  .search-bar { background: var(--card); border-radius: 10px; padding: 14px 16px; margin-bottom: 16px; box-shadow: var(--shadow); display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .search-bar input, .search-bar select { padding: 8px 14px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; outline: none; transition: border .2s; }
  .search-bar input:focus, .search-bar select:focus { border-color: var(--accent); }
  .search-bar input { flex: 1; min-width: 180px; }
  .search-bar select { min-width: 120px; }
  .search-bar .count { font-size: 13px; color: var(--muted); margin-left: auto; }

  .date-group { margin-bottom: 20px; }
  .date-header { font-size: 15px; font-weight: 700; color: var(--accent); padding: 8px 0; border-bottom: 2px solid var(--accent); margin-bottom: 8px; display: flex; justify-content: space-between; }
  .date-header .cnt { font-size: 13px; font-weight: 400; color: var(--muted); }

  .item { background: var(--card); border-radius: 10px; padding: 14px 18px; margin-bottom: 8px; box-shadow: var(--shadow); transition: transform .15s; }
  .item:hover { transform: translateX(4px); }
  .item .title { font-size: 15px; font-weight: 600; line-height: 1.5; margin-bottom: 6px; }
  .item .title a { color: var(--text); text-decoration: none; }
  .item .title a:hover { color: var(--accent); }
  .item .meta { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--muted); align-items: center; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .tag-source { background: #dfe6e9; color: #2d3436; }
  .tag-region { background: #ffeaa7; color: #d63031; }
  .tag-type { background: #81ecec; color: #006266; }

  .empty { text-align: center; padding: 40px; color: var(--muted); font-size: 15px; }

  @media (max-width: 600px) {
    .container { padding: 10px; }
    .header { padding: 16px; }
    .header h1 { font-size: 18px; }
    .search-bar { flex-direction: column; }
    .search-bar input, .search-bar select { width: 100%; }
  }
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>📡 铁塔招标信息</h1>
    <div class="sub">数据来源：中国招标投标公共服务平台 · 中国铁塔电子采购平台 · 乙方宝 ｜ 全国范围 · 最近 7 天</div>
  </div>

  <div class="stats">
    <div class="stat"><div class="num" id="statTotal">-</div><div class="label">总条数</div></div>
    <div class="stat"><div class="num" id="statToday">-</div><div class="label">今日新增</div></div>
    <div class="stat"><div class="num" id="statSources">3</div><div class="label">数据源</div></div>
  </div>

  <div class="search-bar">
    <input type="text" id="searchKeyword" placeholder="🔍 搜索标题关键字..." oninput="doFilter()">
    <select id="searchRegion" onchange="doFilter()">
      <option value="">全部省份</option>
    </select>
    <select id="searchBidType" onchange="doFilter()">
      <option value="">全部类型</option>
      <option value="招标公告">招标公告</option>
      <option value="开标记录">开标记录</option>
      <option value="评标公示">评标公示</option>
      <option value="中标公告">中标公告</option>
      <option value="采购公告">采购公告</option>
    </select>
    <span class="count" id="resultCount"></span>
  </div>

  <div id="list"></div>

</div>

<script>
// 省份列表和城市映射
var PROVINCE_LIST = __PROVINCES__;
var CITY_MAP = __CITY_MAP__;
var ALL_ITEMS = __DATA__;

// 初始化
(function() {
  // 地区下拉：只显示省份
  const sel = document.getElementById('searchRegion');
  PROVINCE_LIST.forEach(function(p) {
    const opt = document.createElement('option');
    opt.value = p; opt.textContent = p; sel.appendChild(opt);
  });

  // 统计
  document.getElementById('statTotal').textContent = ALL_ITEMS.length;
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('statToday').textContent = ALL_ITEMS.filter(function(i) { return i.date === today; }).length;

  doFilter();
})();

// 检查 item 的地区是否匹配选中的省份
function matchProvince(item, province) {
  var regions = item.regions || [];
  for (var i = 0; i < regions.length; i++) {
    var r = regions[i];
    if (r === province) return true;
    // 如果该地区是选中省份的下属城市
    if (CITY_MAP[r] === province) return true;
  }
  return false;
}

function doFilter() {
  var kw = (document.getElementById('searchKeyword').value || '').trim().toLowerCase();
  var province = document.getElementById('searchRegion').value;
  var bidType = document.getElementById('searchBidType').value;

  var filtered = ALL_ITEMS;
  if (kw) filtered = filtered.filter(function(i) { return i.title.toLowerCase().indexOf(kw) !== -1; });
  if (province) filtered = filtered.filter(function(i) { return matchProvince(i, province); });
  if (bidType) filtered = filtered.filter(function(i) { return i.bidType === bidType; });

  document.getElementById('resultCount').textContent = '共 ' + filtered.length + ' 条';
  render(filtered);
}

function render(items) {
  var container = document.getElementById('list');
  if (!items.length) {
    container.innerHTML = '<div class="empty">😕 没有匹配的招标信息</div>';
    return;
  }

  var groups = {};
  items.forEach(function(i) {
    (groups[i.date] = groups[i.date] || []).push(i);
  });
  var dates = Object.keys(groups).sort().reverse();

  var html = '';
  dates.forEach(function(date) {
    var dayItems = groups[date];
    html += '<div class="date-group">';
    html += '<div class="date-header"><span>📅 ' + date + '</span><span class="cnt">' + dayItems.length + ' 条</span></div>';
    dayItems.forEach(function(item) {
      var regionTags = (item.regions||[]).map(function(r) { return '<span class="tag tag-region">' + esc(r) + '</span>'; }).join(' ');
      var typeTag = item.bidType ? '<span class="tag tag-type">' + esc(item.bidType) + '</span>' : '';
      html += '<div class="item">';
      html += '<div class="title"><a href="' + esc(item.url) + '" target="_blank" rel="noopener">' + esc(item.title) + '</a></div>';
      html += '<div class="meta">' + typeTag + '<span class="tag tag-source">' + esc(item.source) + '</span>' + regionTags;
      if (item.description) html += '<span>' + esc(item.description) + '</span>';
      html += '</div></div>';
    });
    html += '</div>';
  });

  container.innerHTML = html;
}

function esc(s) {
  var d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# HTTP 服务器
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/items":
            days = int(qs.get("days", [7])[0])
            items = get_items(days)
            body = json.dumps(items, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        items = get_items(7)
        html = HTML.replace("__DATA__", json.dumps(items, ensure_ascii=False))
        html = html.replace("__PROVINCES__", json.dumps(PROVINCES, ensure_ascii=False))
        html = html.replace("__CITY_MAP__", json.dumps(CITY_TO_PROVINCE, ensure_ascii=False))
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_html(output_path: str = "", days: int = 7) -> str:
    """生成静态 HTML 文件（数据嵌入，无需服务器）"""
    items = get_items(days)
    html = HTML.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__PROVINCES__", json.dumps(PROVINCES, ensure_ascii=False))
    html = html.replace("__CITY_MAP__", json.dumps(CITY_TO_PROVINCE, ensure_ascii=False))

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        print(f"  静态 HTML 已生成: {path} ({len(items)} 条数据)")

    return html


def main():
    import sys

    if "--output" in sys.argv or "-o" in sys.argv:
        # 静态输出模式
        idx = sys.argv.index("--output") if "--output" in sys.argv else sys.argv.index("-o")
        path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "output/index.html"
        days = 7
        if "--days" in sys.argv:
            days = int(sys.argv[sys.argv.index("--days") + 1])
        build_html(path, days)
        return

    print(f"\n  铁塔招标信息 Web 前端")
    print(f"  数据库: {DB_PATH}")
    print(f"  访问地址: http://localhost:{PORT}\n")
    print(f"  按 Ctrl+C 停止\n")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
