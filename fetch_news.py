# -*- coding: utf-8 -*-
"""
新闻聚合器 - 采集脚本
抓取 5 个分类的新闻，生成 data.json 供 GitHub Pages 前端读取。
"""
import json
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import feedparser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
TIMEOUT = 15

# ---------- 各分类数据源 ----------

def fetch_baidu_hot():
    """百度热搜 - 社会热点"""
    items = []
    try:
        r = requests.get(
            "https://top.baidu.com/api/board?platform=wise&tab=realtime",
            headers=HEADERS, timeout=TIMEOUT,
        )
        data = r.json()
        raw = data["data"]["cards"][0]["content"][0]["content"]
        for i, it in enumerate(raw[:30]):
            word = it.get("word", "").strip()
            if not word:
                continue
            items.append({
                "title": word,
                "url": it.get("url", ""),
                "summary": "",
                "source": "百度热搜",
                "time": "",
                "hot": it.get("hotTag", ""),
            })
    except Exception as e:
        print(f"[百度热搜] 失败: {e}")
    return items


def fetch_rss(name, url, category):
    """通用 RSS 抓取"""
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        d = feedparser.parse(r.content)
        for e in d.entries[:25]:
            title = e.get("title", "").strip()
            if not title:
                continue
            summary = e.get("summary", "") or e.get("description", "")
            # 去掉 HTML 标签
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            if len(summary) > 160:
                summary = summary[:157] + "..."
            pub = e.get("published", "") or e.get("updated", "")
            items.append({
                "title": title,
                "url": e.get("link", ""),
                "summary": summary,
                "source": name,
                "time": pub,
                "hot": "",
            })
    except Exception as e:
        print(f"[{name}] 失败: {e}")
    return items


def fetch_sina_sports():
    """新浪体育"""
    items = []
    try:
        r = requests.get(
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2510"
            "&num=30&versionNumber=1.2.4&page=1&encode=utf-8",
            headers=HEADERS, timeout=TIMEOUT,
        )
        data = r.json()
        for it in data["result"]["data"]:
            title = it.get("title", "").strip()
            if not title:
                continue
            summary = it.get("summary") or it.get("intro") or ""
            if len(summary) > 160:
                summary = summary[:157] + "..."
            ctime = it.get("ctime", "")
            tstr = ""
            if ctime:
                try:
                    tstr = datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    tstr = str(ctime)
            items.append({
                "title": title,
                "url": it.get("url", ""),
                "summary": summary,
                "source": it.get("media_name", "新浪体育"),
                "time": tstr,
                "hot": "",
            })
    except Exception as e:
        print(f"[新浪体育] 失败: {e}")
    return items


def fetch_netease_music():
    """网易云新歌榜"""
    items = []
    try:
        r = requests.get(
            "https://music.163.com/api/playlist/detail?id=2884035",
            headers={**HEADERS, "Referer": "https://music.163.com/"},
            timeout=TIMEOUT,
        )
        data = r.json()
        tracks = data["result"]["tracks"]
        for t in tracks[:30]:
            name = t.get("name", "").strip()
            if not name:
                continue
            artists = "/".join(a.get("name", "") for a in t.get("artists", [])[:3])
            sid = t.get("id", "")
            items.append({
                "title": f"{name} - {artists}" if artists else name,
                "url": f"https://music.163.com/#/song?id={sid}" if sid else "",
                "summary": f"歌手：{artists}" if artists else "",
                "source": "网易云音乐",
                "time": "",
                "hot": "",
            })
    except Exception as e:
        print(f"[网易云音乐] 失败: {e}")
    return items


def fetch_douban_movie():
    """豆瓣电影热门"""
    items = []
    try:
        r = requests.get(
            "https://movie.douban.com/j/search_subjects?type=movie"
            "&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit=25&page_start=0",
            headers={**HEADERS, "Referer": "https://movie.douban.com/"},
            timeout=TIMEOUT,
        )
        data = r.json()
        for s in data.get("subjects", []):
            title = s.get("title", "").strip()
            if not title:
                continue
            rate = s.get("rate", "")
            items.append({
                "title": f"{title}（豆瓣 {rate}）" if rate else title,
                "url": s.get("url", ""),
                "summary": f"评分：{rate}" if rate else "",
                "source": "豆瓣电影",
                "time": "",
                "hot": "",
            })
    except Exception as e:
        print(f"[豆瓣电影] 失败: {e}")
    return items


# ---------- 分类配置 ----------

CATEGORIES = {
    "hot": {
        "name": "热点",
        "icon": "🔥",
        "sources": [("百度热搜", fetch_baidu_hot)],
    },
    "tech": {
        "name": "AI科技",
        "icon": "🤖",
        "sources": [
            ("IT之家", lambda: fetch_rss("IT之家", "https://www.ithome.com/rss/", "tech")),
            ("爱范儿", lambda: fetch_rss("爱范儿", "https://www.ifanr.com/feed", "tech")),
            ("少数派", lambda: fetch_rss("少数派", "https://sspai.com/feed", "tech")),
            ("开源中国", lambda: fetch_rss("开源中国", "https://www.oschina.net/news/rss", "tech")),
            ("HackerNews", lambda: fetch_rss("HackerNews", "https://hnrss.org/frontpage", "tech")),
        ],
    },
    "sports": {
        "name": "体育",
        "icon": "⚽",
        "sources": [("新浪体育", fetch_sina_sports)],
    },
    "music": {
        "name": "音乐",
        "icon": "🎵",
        "sources": [("网易云音乐", fetch_netease_music)],
    },
    "film": {
        "name": "影视",
        "icon": "🎬",
        "sources": [("豆瓣电影", fetch_douban_movie)],
    },
}


def dedup(items):
    """按 URL / 标题哈希去重"""
    seen = set()
    out = []
    for it in items:
        key = it.get("url") or hashlib.md5(it["title"].encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def main():
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "categories": {},
    }

    # 并发抓取所有源
    tasks = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for cat_key, cat in CATEGORIES.items():
            for src_name, fn in cat["sources"]:
                tasks.append((cat_key, src_name, ex.submit(fn)))

        for cat_key, src_name, fut in tasks:
            try:
                items = fut.result()
            except Exception as e:
                print(f"[{src_name}] 异常: {e}")
                items = []
            if cat_key not in result["categories"]:
                result["categories"][cat_key] = {
                    "name": cat["name"],
                    "icon": cat["icon"],
                    "items": [],
                }
            result["categories"][cat_key]["items"].extend(items)
            print(f"[{src_name}] 抓到 {len(items)} 条")

    # 去重 + 限制每条最多 30 条
    for cat_key in result["categories"]:
        cat = result["categories"][cat_key]
        cat["items"] = dedup(cat["items"])[:30]

    # 写入 data.json
    out_path = "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    total = sum(len(c["items"]) for c in result["categories"].values())
    print(f"\n✅ 完成，共 {total} 条，已写入 {out_path}")
    print(f"生成时间：{result['generated_at']}")


if __name__ == "__main__":
    main()
