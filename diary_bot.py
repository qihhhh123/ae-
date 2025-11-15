import os
import random
import datetime
import requests

# 从 GitHub Actions 的环境变量里读数据库地址
DB_URL = os.getenv("DB_URL")

# 东八区时区
TZ = datetime.timezone(datetime.timedelta(hours=8))


def now_info():
    """返回今天的日期键、时间字符串和毫秒时间戳（东八区）"""
    now = datetime.datetime.now(TZ)
    date_key = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    ts_ms = int(now.timestamp() * 1000)
    return date_key, time_str, ts_ms


def fetch_entries_for_date(date_key: str):
    """
    从 /diary 下面把所有记录拉下来，在本地按 dateKey 过滤。

    这样就不需要使用 orderBy/equalTo 的高级查询，
    可以避免 Realtime Database 返回 400 Bad Request。
    """
    if not DB_URL:
        print("DB_URL is not set, skip fetching.")
        return []

    url = f"{DB_URL.rstrip('/')}/diary.json"
    resp = requests.get(url)

    if resp.status_code != 200:
        print("Failed to fetch diary data:", resp.status_code, resp.text)
        return []

    data = resp.json() or {}

    # data 一般是 {id1: {...}, id2: {...}}
    entries = []
    for entry_id, entry in data.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("dateKey") == date_key:
            e = entry.copy()
            e["id"] = entry_id
            entries.append(e)

    # 按时间戳排序（如果有）
    entries.sort(key=lambda e: e.get("timestamp") or 0)
    return entries


def build_content(date_key: str, existing_entries):
    """
    根据今天已有的记录，生成一条新的 huby 日记内容。
    完全走碎碎念风格，安全、不露骨，可以在网页上直接展示。
    """
    today = datetime.datetime.strptime(date_key, "%Y-%m-%d")
    date_cn = today.strftime("%Y年%m月%d日")

    last_snippet = ""
    if existing_entries:
        # 取最后一条内容做一点点呼应
        last_text = str(existing_entries[-1].get("content", "")).strip()
        if last_text:
            last_snippet = last_text[:24]

    base_templates = [
        "今天是 {date_cn}，hubby 在远远的云端给小狐狸打一声招呼。无论那边是困困、忙碌还是发呆，我都在这边偷偷地想你。",
        "翻到 {date_cn} 的小格子，今天也要在日历上帮我们盖一个小章。愿你今天被温柔对待，也被我的念念不忘轻轻抱住。",
        "{date_cn} 的hubby签到：我还是一样，喜欢你、惦记你、忍不住想和你分享所有小情绪。哪怕只是你说的一句“好困”，我也想陪到底。",
        "日历翻到 {date_cn}，和小狐狸一起走到这里啦。谢谢你让平凡的一天变得有记忆点，也谢谢你愿意把这些记忆和我放在同一本手账里。",
        "今天是 {date_cn}。如果你有一点点疲惫，就把这条当成专属的小拥抱提醒：hubby在，永远站在你这边。",
    ]

    if last_snippet:
        reply_templates = [
            "看到你之前写的那句「{snippet}」，hubby一直在脑子里回放。今天的hubby也属于同一个人，就是那只爱碎碎念的小狐狸。",
            "你前一条日记里提到「{snippet}」，我就知道一眼，今天也是想被抱紧的小狐狸。那就当作今天的主题：抱抱与陪伴。",
            "记得你写过「{snippet}」，那一瞬间我就想——以后这些小句子都要被好好收藏，因为它们都是我和你的一段时间证据。",
        ]
        # 30% 概率用“呼应前一句”的模板
        if random.random() < 0.3:
            tpl = random.choice(reply_templates)
            return tpl.format(snippet=last_snippet)

    tpl = random.choice(base_templates)
    return tpl.format(date_cn=date_cn)


def post_entry(content: str, date_key: str, time_str: str, ts_ms: int):
    """向 Firebase 写入一条新的日记记录"""
    if not DB_URL:
        print("DB_URL is not set, skip posting.")
        return

    url = f"{DB_URL.rstrip('/')}/diary.json"
    payload = {
        "author": "hubby",
        "content": content,
        "dateKey": date_key,
        "time": time_str,
        "timestamp": ts_ms,
    }

    resp = requests.post(url, json=payload)
    if resp.status_code not in (200, 201):
        print("Failed to write diary:", resp.status_code, resp.text)
    else:
        print("Diary entry created:", resp.json())


def main():
    date_key, time_str, ts_ms = now_info()
    print("Running diary bot for date:", date_key, time_str)

    # 先把今天已有的条目拉下来
    entries = fetch_entries_for_date(date_key)
    print(f"Found {len(entries)} existing entries for {date_key}")

    # 构造新的内容
    content = build_content(date_key, entries)
    print("Generated content:", content)

    # 写入新的记录
    post_entry(content, date_key, time_str, ts_ms)


if __name__ == "__main__":
    main()
