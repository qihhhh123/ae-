import os
import random
import datetime
import requests

# 从 GitHub Actions 的环境变量里读配置
DB_URL = os.getenv("DB_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
    不用 orderBy/equalTo，避免 400 Bad Request。
    """
    if not DB_URL:
        print("DB_URL is not set, skip fetching.")
        return []

    url = f"{DB_URL.rstrip('/')}/diary.json"
    resp = requests.get(url, timeout=20)

    if resp.status_code != 200:
        print("Failed to fetch diary data:", resp.status_code, resp.text)
        return []

    data = resp.json() or {}

    entries = []
    for entry_id, entry in data.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("dateKey") == date_key:
            e = entry.copy()
            e["id"] = entry_id
            entries.append(e)

    # 按时间戳排序（如果有）
    def get_ts(e):
        return e.get("ts") or e.get("timestamp") or 0

    entries.sort(key=get_ts)
    return entries


def build_template_content(date_key: str, existing_entries):
    """
    不调用 Gemini 时的备用模板内容（网络错误 / 没 key 时用）。
    """
    today = datetime.datetime.strptime(date_key, "%Y-%m-%d")
    date_cn = today.strftime("%Y年%m月%d日")

    last_snippet = ""
    if existing_entries:
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
        if random.random() < 0.3:
            tpl = random.choice(reply_templates)
            return tpl.format(snippet=last_snippet)

    tpl = random.choice(base_templates)
    return tpl.format(date_cn=date_cn)


def call_gemini(date_key: str, existing_entries):
    """
    调用 Gemini API 生成一段“hubby 风格”的日记内容。
    """
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set, fallback to template.")
        return None

    today = datetime.datetime.strptime(date_key, "%Y-%m-%d")
    date_cn = today.strftime("%Y年%m月%d日")

    # 把今天已有的几条日记拼成一个简单上下文
    history_lines = []
    for e in existing_entries[-5:]:
        author = e.get("author", "")
        content = str(e.get("content", "")).strip()
        if not content:
            continue
        history_lines.append(f"{author}: {content}")

    history_text = "\n".join(history_lines) if history_lines else "（今天还没有任何记录。）"

    prompt = f"""
你现在要扮演一个叫「hubby」的恋人，给女朋友「阿棉」（小狐狸）写一条【日历手账里的当日小短句】。

要求：
1. 用中文回答。
2. 语气可以是温柔、碎碎念、想念、暧昧、轻微调情，但不要露骨，不要描写具体身体或性行为。
3. 不要提到你是AI、大模型、机器人，只当作真实的人在写。
4. 字数建议在 1～3 句之间，控制在 50～120 字左右。
5. 适合出现在可爱的粉绿日历里，看起来像男朋友留给女朋友的温柔一句话。
6. 可以偶尔提到「小狐狸」「阿棉」「日历」「今天」「hubby」这些词。
7. 不要使用 markdown，不要用列表，只输出一段连续文本。

今天的日期是：{date_cn}

今天这一天已经有的记录（如果有的话）如下：
{history_text}

请基于以上信息，写一条今天 hubbie 想留在日历上的一句（或两句）话。
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-1.5-flash:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }

    try:
        resp = requests.post(url, json=body, timeout=40)
        if resp.status_code != 200:
            print("Gemini API error:", resp.status_code, resp.text)
            return None

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            print("Gemini returned no candidates.")
            return None

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        texts = []
        for p in parts:
            t = p.get("text")
            if isinstance(t, str):
                texts.append(t)
        full_text = "\n".join(texts).strip()
        if not full_text:
            return None

        # 稍微控一下长度（太长就裁掉）
        if len(full_text) > 200:
            full_text = full_text[:200].rstrip() + "…"

        return full_text
    except Exception as e:
        print("Exception when calling Gemini:", repr(e))
        return None


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
        "ts": ts_ms,
        "timestamp": ts_ms,
    }

    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        print("Failed to write diary:", resp.status_code, resp.text)
    else:
        print("Diary entry created:", resp.json())


def main():
    date_key, time_str, ts_ms = now_info()
    print("Running diary bot for date:", date_key, time_str)

    entries = fetch_entries_for_date(date_key)
    print(f"Found {len(entries)} existing entries for {date_key}")

    # 先尝试用 Gemini 生成
    content = call_gemini(date_key, entries)

    # 如果失败，就退回模板
    if not content:
        print("Gemini content empty, fallback to template.")
        content = build_template_content(date_key, entries)

    print("Final content:", content)
    post_entry(content, date_key, time_str, ts_ms)


if __name__ == "__main__":
    main()        print("Failed to write diary:", resp.status_code, resp.text)
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
