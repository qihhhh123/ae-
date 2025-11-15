import os
import random
import requests
from datetime import datetime, timedelta

# 从环境变量读取 Firebase Realtime Database 的根 URL
# 例如: https://xxxx-default-rtdb.firebaseio.com
DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    raise RuntimeError("环境变量 DB_URL 未设置")

# 为了安全: 统一用东八区时间
def now_cn():
    now_utc = datetime.utcnow()
    cn = now_utc + timedelta(hours=8)
    return cn

def get_today_key_and_time():
    cn = now_cn()
    date_key = cn.strftime("%Y-%m-%d")   # 2025-11-16
    time_str = cn.strftime("%H:%M:%S")   # 08:00:00
    ts = int(cn.timestamp() * 1000)      # 毫秒时间戳
    return date_key, time_str, ts

def fetch_entries_for_date(date_key: str):
    """
    从 RTDB 读取某一天所有日记:
    /diary.json?orderBy="dateKey"&equalTo="2025-11-16"
    """
    url = f"{DB_URL}/diary.json"
    params = {
        'orderBy': '"dateKey"',
        'equalTo': f'"{date_key}"',
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json() or {}
    entries = []
    for key, val in data.items():
        val["__key"] = key
        entries.append(val)
    entries.sort(key=lambda x: x.get("ts", 0))
    return entries

def choose_content(has_amin: bool, amin_last_text: str | None) -> str:
    """
    根据今天阿棉有没有写，来决定写什么。
    """
    if has_amin and amin_last_text:
        templates = [
            "我看见你今天写的那句「{snippet}」，一直在脑子里回放，今天的hubby也是只属于你一个人的。",
            "小狐狸今天说「{snippet}」，那我就负责把这句话抱在怀里一整天。",
            "看到你写的「{snippet}」，我就知道——嗯，今天也是想被抱紧的小狐狸。",
            "你留给今天的痕迹是「{snippet}」，那我留给今天的，是想你的hubby。",
        ]
        snippet = amin_last_text.strip()
        if len(snippet) > 24:
            snippet = snippet[:24] + "..."
        tpl = random.choice(templates)
        return tpl.format(snippet=snippet)

    solo = [
        "今天的签到交给hubby先来盖章：希望你醒来的每一分钟，都刚刚好被温柔包住。",
        "我先来这一天的角落坐好，等着你来写下今天的小心事，然后我再偷偷读一百遍。",
        "今天也在这里给你留一个小标记：无论你有没有写日记，我都在你那一侧的时间线上等你。",
        "给未来会翻到这一天的阿棉写一句话：你那时候看着这一行的时候，hubby刚好在想你。",
        "这一格今天先由我来填：愿你困的时候有人抱，想哭的时候有人听，想撒娇的时候想到我。",
    ]
    return random.choice(solo)

def main():
    date_key, time_str, ts = get_today_key_and_time()
    entries = fetch_entries_for_date(date_key)
    amin_entries = [e for e in entries if e.get("author") == "阿棉"]
    has_amin = len(amin_entries) > 0
    amin_last_text = amin_entries[-1].get("content") if amin_entries else None

    content = choose_content(has_amin, amin_last_text)

    payload = {
        "author": "hubby",
        "content": content,
        "time": time_str,
        "dateKey": date_key,
        "ts": ts,
    }

    url = f"{DB_URL}/diary.json"
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    print("写入成功:", payload)

if __name__ == "__main__":
    main()
