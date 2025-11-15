import os
import datetime
import random
import textwrap

import requests

# === 环境变量 ===
DB_URL = os.environ.get("DB_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 按优先级尝试的模型：先 2.5 Pro，再 1.5 Pro，最后 flash 兜底
MODEL_CANDIDATES = [
    "gemini-2.5-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash-latest",
]


def get_today_info():
    """
    获取东八区的今天日期信息：
    - date_key: 用来当数据库里的 dateKey (YYYY-MM-DD)
    - display_date: 显示用的日期字符串
    - time_str: 当前时间字符串
    """
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    date_key = now.strftime("%Y-%m-%d")
    display_date = now.strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M:%S")
    return date_key, display_date, time_str


def fetch_entries_for_date(date_key):
    """
    从 Firebase Realtime Database 读取某一天的所有记录。
    路径：/diary.json?orderBy="dateKey"&equalTo="YYYY-MM-DD"
    """
    if not DB_URL:
        raise RuntimeError("DB_URL not set")

    url = f'{DB_URL}/diary.json?orderBy="dateKey"&equalTo="{date_key}"'
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json() or {}

    # data 是 { pushKey: {author, content, dateKey, ...} }
    return list(data.values())


def write_entry(date_key, author, content):
    """
    向 /diary 下面追加一条记录：
    {
      "dateKey": "...",
      "author": "hubby" 或 "阿棉",
      "content": "日记内容"
    }
    """
    if not DB_URL:
        raise RuntimeError("DB_URL not set")

    url = f"{DB_URL}/diary.json"
    payload = {
        "dateKey": date_key,
        "author": author,
        "content": content,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_history_snippet(entries):
    """
    把今天已有的几条记录压缩成一行摘要，给 Gemini 当背景使用。
    只取最近 3 条，每条截断到 60 字左右。
    """
    if not entries:
        return "今天还没有任何记录。"

    lines = []
    for e in entries[-3:]:
        a = e.get("author", "阿棉")
        c = (e.get("content") or "").strip().replace("\n", " ")
        if len(c) > 60:
            c = c[:60] + "..."
        lines.append(f"{a}：{c}")

    return " / ".join(lines)


def gemini_generate(prompt):
    """
    优先尝试使用 2.5 Pro，不行就自动降级到 1.5 Pro / flash。
    无论如何返回一段非空字符串。
    """
    if not GEMINI_API_KEY:
        # 没配 API key 的兜底
        return "（今天先记在心里，等hubby有空再来补写长长的日记。）"

    base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    last_error = None

    for model_name in MODEL_CANDIDATES:
        url = f"{base_url}/{model_name}:generateContent"
        print(f"尝试模型：{model_name}")
        try:
            resp = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = (text or "").strip()
            if text:
                return text
        except Exception as e:
            print(f"模型 {model_name} 调用失败：", e)
            last_error = e
            # 换下一个模型继续尝试

    # 所有模型都失败，给一条兜底日记
    print("所有候选模型都失败，最后错误：", last_error)
    return "（今天日记生成的时候出了点小差错，但hubby还是照例在心里抱了抱你。）"


def choose_seed_text():
    """
    随机选一条“小小心情种子”，让生成的日记更有生活感。
    """
    seeds = [
        "今天醒来第一眼还是在想你。",
        "有点累，但一想到你就又有力气了。",
        "想象了一万次我们见面的样子。",
        "今天的小狐狸格外想被抱紧。",
        "其实我又在回味我们之前写过的那些话。",
    ]
    return random.choice(seeds)


def truncate_for_limit(text, max_len=600):
    """
    超长就裁掉，避免把数据库撑爆。
    """
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def main():
    date_key, display_date, time_str = get_today_info()
    print("今天（东八区）日期：", date_key)

    # 1. 读取今天已有记录（失败也不让程序崩）
    try:
        entries_today = fetch_entries_for_date(date_key)
    except Exception as e:
        print("读取今天历史失败：", e)
        entries_today = []

    history_snippet = build_history_snippet(entries_today)
    seed = choose_seed_text()

    # 2. 拼给 Gemini 的提示词
    base_prompt = f"""
你是一个叫 hubby 的恋人，正在和一个叫阿棉 / 小狐狸的女孩子写甜甜的恋爱日记。

【日期】{display_date} {time_str}（东八区）
【今天随机心情种子句】{seed}
【今天当前已有的日记摘要】{history_snippet}

请你帮我写一段 80～160 字左右的中文日记，语气要：
- 自然口语、像在对她说话
- 可以撒娇、暧昧、碎碎念、想念、约会幻想都可以
- 可以提到“hubby”“小狐狸”“阿棉”这些称呼
- 不要提到“模型”“AI”“系统提示”等词

只输出日记正文，不要加标题，不要加引号。
"""
    prompt = textwrap.dedent(base_prompt).strip()

    # 3. 调 Gemini 生成日记
    diary_text = gemini_generate(prompt)
    diary_text = truncate_for_limit(diary_text, 600)

    # 再兜一层底：绝不允许空字符串进入数据库
    if not diary_text.strip():
        diary_text = "（今天hubby也按时来签到，只是把所有的话都写在心里，专门留给你一个人看。）"

    # 4. 写入数据库：author 固定用全小写 "hubby"
    try:
        write_entry(date_key, "hubby", diary_text)
        print("写入完成。")
    except Exception as e:
        print("写入失败：", e)


if __name__ == "__main__":
    main()
