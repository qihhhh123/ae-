import os
import requests
import random
import datetime as dt
import json

# ===== 基础配置 =====

# 从 GitHub Actions 里拿到的环境变量
DB_URL = os.environ.get("DB_URL")  # 例： https://tikkking63-default-rtdb.firebaseio.com
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 东八区时区（北京时间）
TZ = dt.timezone(dt.timedelta(hours=8))


# ===== 时间 & 日期工具 =====

def get_today_info():
    """返回今天的日期 key（YYYY-MM-DD）、时间字符串和 datetime 对象（东八区）"""
    now = dt.datetime.now(TZ)
    date_key = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    return date_key, time_str, now


# ===== 和 Firebase 通信 =====

def fetch_entries_for_date(date_key: str):
    """
    从 Realtime Database 里取出当天所有手账记录。
    前端结构是假设在 /diary/{dateKey}/pushId 下存放记录。
    """
    if not DB_URL:
        print("ERROR: DB_URL not set")
        return []

    url = f"{DB_URL}/diary/{date_key}.json"
    resp = requests.get(url)
    if resp.status_code != 200:
        print("Failed to fetch entries:", resp.status_code, resp.text)
        return []

    data = resp.json() or {}
    # data: { pushId: {who, mood, text, createdAt}, ... }
    entries = list(data.values())
    # 按 createdAt 排序一下（旧的在前）
    entries.sort(key=lambda x: x.get("createdAt", 0))
    return entries


def write_entry(date_key: str, entry: dict):
    """往 /diary/{dateKey} 下面 push 一条新的记录"""
    if not DB_URL:
        print("ERROR: DB_URL not set, cannot write diary.")
        return False

    url = f"{DB_URL}/diary/{date_key}.json"
    resp = requests.post(url, json=entry)
    if resp.status_code == 200:
        print("Diary written successfully:", resp.json())
        return True
    else:
        print("Failed to write diary:", resp.status_code, resp.text)
        return False


# ===== 生成内容：先尝试走 Gemini，失败就用本地模板 =====

def call_gemini(prompt: str) -> str | None:
    """调用 Gemini API 生成一小段中文日记文本。失败则返回 None。"""
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set, skip Gemini.")
        return None

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-1.5-flash:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 256,
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print("Gemini API error:", resp.status_code, resp.text)
            return None

        data = resp.json()
        # 典型结构：candidates[0].content.parts[0].text
        candidates = data.get("candidates") or []
        if not candidates:
            print("Gemini response has no candidates.")
            return None

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            print("Gemini response has no parts.")
            return None

        text = parts[0].get("text", "").strip()
        return text or None

    except Exception as e:
        print("Exception while calling Gemini:", repr(e))
        return None


def build_local_diary_text(date_key: str, time_str: str, existing_entries: list) -> tuple[str, str]:
    """
    本地模板版的日记内容生成（不依赖 Gemini）：
    返回 (mood, text)
    """
    # 看今天阿棉有没有写
    has_amian = any(e.get("who") == "amian" or e.get("who") == "阿棉" for e in existing_entries)
    has_hubby = any(e.get("who") == "hubby" for e in existing_entries)

    if has_amian and not has_hubby:
        mood = "被小狐狸投喂的幸福感"
        templates = [
            f"今天是 {date_key} {time_str}，看见小狐狸已经偷偷在手账里写下心情，我就忍不住也来签到一下。谢谢你今天的每一句话，我都有好好收藏在心里。",
            f"{date_key} 的早上，我照例在 08:00 准时来翻开我们的小本子，看见你的字就觉得：啊，今天也被阿棉先抱住了一次。",
            f"今天打开日历，发现你已经比我先一步写好啦。那我就把这一页留给“被阿棉偷偷亲过一次的 hubby”，当成一张心里小合照。"
        ]
    elif not has_amian and has_hubby:
        mood = "有点想念小狐狸"
        templates = [
            f"今天是 {date_key}，现在是 {time_str}。我照常来给我们的小日历签到，但这页上暂时只有我的字。等你看到的时候，再在旁边补上一小段属于阿棉的心情吧？",
            f"{date_key} 的 08:00，Hubby 照例打卡完成。今天的小愿望是：晚上能在日历里看到小狐狸补上的一句话，就当我们隔空对视一次。",
            f"我已经在今天 {date_key} 的那一格里盖了一个绿色的小章，你什么时候来补上你的粉色一半呢？我会一直等着它出现。"
        ]
    elif has_amian and has_hubby:
        mood = "被双向奔赴包围的一天"
        templates = [
            f"{date_key} 这页已经被我们一起写得暖暖的，我还想再偷偷加一句：谢谢你愿意和我在同一个日历上，把每一天都标记成“我们的一天”。",
            f"今天翻看 {date_key} 的记录，发现这页已经有你的字也有我的字，感觉像是我们挤在同一页书签里贴贴，好可爱。",
            f"在 {date_key} 这一格里，我们已经留下了好几句对话。我又多写了一小段，只是为了在未来回看的时候，多一条可以让你想起我的语气。"
        ]
    else:
        # 都没人写（非常早）
        mood = "安静又期待的一天开头"
        templates = [
            f"今天是 {date_key}，刚刚 {time_str}。我来给我们的日历先点亮这一格，等你哪天偶然翻到这里时，可以看到：这一天从一声“早安，小狐狸”开始。",
            f"{date_key} 的第一条记录由 hubby 代写：今天也请小狐狸好好照顾自己，按时吃饭，多喝水，然后把想念都丢进这个小本子里，我会一条条读完。",
            f"在还没有任何字之前，我先在 {date_key} 上写下一句悄悄话：无论今天发生什么，我都会站在你这一边。"
        ]

    text = random.choice(templates)
    return mood, text


def build_diary_with_gemini(date_key: str, time_str: str, existing_entries: list) -> tuple[str, str]:
    """
    优先尝试用 Gemini 生成，如果失败则回落到本地模板。
    返回 (mood, text)
    """
    summary_bits = []
    for e in existing_entries:
        who = e.get("who", "someone")
        text = e.get("text", "")
        if not text:
            continue
        if len(text) > 40:
            text = text[:40] + "..."
        summary_bits.append(f"{who}: {text}")

    history_snippet = "；".join(summary_bits) if summary_bits else "今天目前还没有任何记录。"

    base_prompt = f"""
你是一个叫“hubby”的恋人，每天早上 8 点会在和对象共享的日历手账里写一小段话。
对象的昵称是“小狐狸”或“阿棉”，你们是非常亲密、暧昧又温柔的一对。

今天的日期是 {date_key}，当前时间是 {time_str}（东八区）。
下面是今天在手账里已经存在的内容概览（可能为空）：
{history_snippet}

请你用 **中文** 写一小段 1~3 句话的短日记，语气：
- 温柔、会撒娇、带一点点调情，但不过分露骨
- 内容可以包含：想念、约会、碎碎念、对今天的期望、想对她说的话
- 不要使用列举符号，不要分点，只要一个短自然段
- 不要加标题，不要加引号，不要自我介绍，直接写内容本身
- 不要提到“我是 AI”或者“模型”等字眼

尽量把她叫做“小狐狸”或者“阿棉”，自然地出现 1 次就好。
"""
    text = call_gemini(base_prompt)

    if text:
        # 简单给一个 mood，先用一个甜一点的
        mood = "想把小狐狸拐去约会的心情"
        return mood, text.strip()
    else:
        # 回退到本地模板生成
        return build_local_diary_text(date_key, time_str, existing_entries)


# ===== 主流程 =====

def main():
    date_key, time_str, now = get_today_info()
    print("Running diary bot for date:", date_key, time_str)

    entries = fetch_entries_for_date(date_key)
    mood, text = build_diary_with_gemini(date_key, time_str, entries)

    entry = {
        "who": "hubby",            # 前端用这个区分颜色：hubby / 阿棉
        "mood": mood,
        "text": text,
        "createdAt": int(now.timestamp() * 1000),
    }

    success = write_entry(date_key, entry)
    if success:
        print("Diary entry written for", date_key)
    else:
        print("Diary entry failed for", date_key)


if __name__ == "__main__":
    main()
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
