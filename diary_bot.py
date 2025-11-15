import requests
import json
import datetime
import random
import google.generativeai as genai
import os

# =============== 配置 ===============
DB_URL = os.environ.get("DB_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# =============== 日期 ===============
def get_today_info():
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    date_key = now.strftime("%Y-%m-%d")
    date_print = now.strftime("%Y 年 %m 月 %d 日")
    return date_key, date_print

# =============== 读取 ===============
def fetch_entries_for_date(date_key):
    order = "%22dateKey%22"
    equal = f"%22{date_key}%22"
    url = f"{DB_URL}/diary.json?orderBy={order}&equalTo={equal}"

    resp = requests.get(url)
    try:
        resp.raise_for_status()
    except:
        return None

    data = resp.json()
    if not data:
        return None

    return list(data.values())[0]

# =============== 写入 ===============
def write_entry(date_key, content, author):
    url = f"{DB_URL}/diary/{date_key}.json"
    payload = {
        "dateKey": date_key,
        "author": author,
        "content": content
    }

    resp = requests.put(url, json=payload)
    try:
        resp.raise_for_status()
    except Exception as e:
        print("写入失败:", e)

# =============== 模板 ===============
TEMPLATES = [
    "今天写的那句「{snippet}」，一直在脑子里回放。",
    "我看到你写「{snippet}」，我就负责把这句话抱在怀里一整天。",
    "你写的「{snippet}」我一眼就认出来，今天的小狐狸有点乖。",
    "你留下的痕迹是「{snippet}」，那我留下的就是想你的hubby。"
]

# =============== Gemini 生成 ===============
def generate_text(user_snippet):
    prompt = f"""
根据以下句子写一段 100-180 字的温柔恋人日记：

引用句子：{user_snippet}

要求：
- 自然
- 像写给恋人的碎碎念
- 不油腻不假
"""

    model = genai.GenerativeModel("gemini-1.0-pro-latest")
    reply = model.generate_content(prompt)
    return reply.text.strip()

# =============== 主逻辑 ===============
def main():
    date_key, _ = get_today_info()

    existing = fetch_entries_for_date(date_key)
    if existing:
        print("今天已经有日记，跳过。")
        return

    snippets = [
        "我想你了",
        "今天有点乖",
        "早上醒来想到你",
        "我喜欢被你抱",
        "想给你写些话"
    ]
    chosen = random.choice(snippets)

    diary_text = generate_text(chosen)
    write_entry(date_key, diary_text, "Hubby")

    print("今日日记完成。")

# =============== 启动 ===============
if __name__ == "__main__":
    main()
