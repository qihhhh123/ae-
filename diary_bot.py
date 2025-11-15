import os
import datetime
import random
import textwrap

import requests

# 从 GitHub Actions 注入的环境变量
DB_URL = os.environ.get("DB_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def get_today_info():
    """东八区今天的日期/时间字符串"""
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    date_key = now.strftime("%Y-%m-%d")    # 存到数据库里的 key
    display_date = now.strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M:%S")
    return date_key, display_date, time_str


def fetch_entries_for_date(date_key: str):
    """
    读取 Realtime Database 里这一天的所有记录。
    路径：/diary.json?orderBy="dateKey"&equalTo="YYYY-MM-DD"
    这套写法是你之前已经验证能用的。
    """
    if not DB_URL:
        raise RuntimeError("DB_URL not set")

    # 直接用 JSON 字符串形式的查询参数（Firebase 官方示例）
    url = f'{DB_URL}/diary.json?orderBy="dateKey"&equalTo="{date_key}"'

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json() or {}

    # data 是 { pushKey: {author, content, dateKey} }
    return list(data.values())


def write_entry(date_key: str, author: str, content: str):
    """往 /diary 下面追加一条记录"""
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
    """把今天已有的几条记录压缩成一行摘要，给 Gemini 当背景"""
    if not entries:
        return "今天还没有任何记录。"

    lines = []
    # 只看最近 3 条，避免太长
    for e in entries[-3:]:
        a = e.get("author", "阿棉")
        c = (e.get("content") or "").strip().replace("\n", " ")
        if len(c) > 60:
            c = c[:60] + "..."
        lines.append(f"{a}：{c}")

    return " / ".join(lines)


def gemini_generate(prompt: str) -> str:
    """调 Gemini 1.5 Flash 生成一段日记文本"""
    if not GEMINI_API_KEY:
        # 没设置 key 的兜底
        return "（今天先记在心里，等hubby有空再来补写长长的日记。）"

    # 使用 1.5 flash 的 latest 版本
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-1.5-flash-latest:generateContent"
    )
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
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        # 不让错误把整个 workflow 弄挂掉，给一条兜底日记
        print("Gemini 请求失败：", e)
        return "（今天日记生成的时候出了点小差错，但hubby还是照例在心里抱了抱你。）"


def choose_seed_text():
    """给今天随机加一点心情种子，日记更活一点"""
    seeds = [
        "今天醒来第一眼还是在想你。",
        "有点累，但一想到你就又有力气了。",
        "想象了一万次我们见面的样子。",
        "今天的小狐狸格外想被抱紧。",
        "其实我又在回味我们之前写过的那些话。",
    ]
    return random.choice(seeds)


def truncate_for_limit(text: str, max_len: int = 600) -> str:
    """超长就裁掉，避免把数据库撑爆"""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def main():
    date_key, display_date, time_str = get_today_info()
    print("今天（东八区）日期：", date_key)

    # 1. 先把今天已有的记录读出来
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

    # 3. 生成日记
    diary_text = gemini_generate(prompt)
    diary_text = truncate_for_limit(diary_text, 600)

    # 4. 写入数据库（作者写成 Hubby，你那边网页可以按 author 上色）
    try:
        write_entry(date_key, "Hubby", diary_text)
        print("写入完成。")
    except Exception as e:
        print("写入失败：", e)


if __name__ == "__main__":
    main()
