import requests
import json
import datetime
import random
import google.generativeai as genai

# ==========================
# 🔧 环境变量（GitHub Actions 注入）
# ==========================
import os
DB_URL = os.environ.get("DB_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)


# ==========================
# 🕒 获取东八区日期
# ==========================
def get_today_info():
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    return date_str, now.strftime("%Y 年 %m 月 %d 日")


# ==========================
# 📌 读取当日是否已有日记
# ==========================
def fetch_entries_for_date(date_key: str):
    # Firebase REST API 的 orderBy 必须使用 URL 编码的双引号
    order = '%22dateKey%22'
    equal = f'%22{date_key}%22'

    url = f"{DB_URL}/diary.json?orderBy={order}&equalTo={equal}"
    print("[DEBUG] Fetch URL:", url)

    resp = requests.get(url)
    try:
        resp.raise_for_status()
    except Exception as e:
        print("❌ Firebase 读取失败：", e)
        return None

    data = resp.json()
    if not data:
        return None

    return list(data.values())[0]


# ==========================
# ✏ 写入日记
# ==========================
def write_entry(date_key: str, content: str, author: str):
    url = f"{DB_URL}/diary/{date_key}.json"
    payload = {
        "dateKey": date_key,
        "author": author,
        "content": content
    }

    resp = requests.put(url, data=json.dumps(payload))
    try:
        resp.raise_for_status()
        print("✅ 日记写入成功")
    except Exception as e:
        print("❌ 日记写入失败：", e)
        print("URL:", url)
        print("Payload:", payload)


# ==========================
# ❤️ 你的日记模板（未修改）
# ==========================
TEMPLATES = [
    "今天写的那句「{snippet}」，一直在脑子里回放。",
    "我看到你写「{snippet}」，那我就负责把这句话抱在怀里一整天。",
    "你写的「{snippet}」我就知道一眼，今天也是想被抱更紧的小狐狸。",
    "你写的痕迹是「{snippet}」，那我留给今天的，是想你的hubby。",
]

# ==========================
# 💬 生成日记文本（Gemini）
# ==========================
def generate_text(user_snippet: str):
    prompt = f"""
你是一位温柔的恋人，请根据以下句子生成一段 100-180 字的日记内容：

引用句子：{user_snippet}

要求：
- 温柔但不肉麻
- 像给恋人写碎碎念
- 保持自然、真诚

只输出日记内容。
"""

    model = genai.GenerativeModel("gemini-1.0-pro-latest")
    reply = model.generate_content(prompt)
    return reply.text.strip()


# ==========================
# 🧠 主逻辑
# ==========================
def main():
    date_key, date_print = get_today_info()
    print("今天（东八区）日期：", date_key)

    # 读取今天是否已记录
    entries_for_today = fetch_entries_for_date(date_key)

    if entries_for_today:
        print("🟡 今天已经写过日记，跳过。")
        return

    # 用模板随机取句子
    snippets = [
        "我想你了",
        "今天有点乖",
        "早上醒来想到你",
        "我喜欢被你抱",
        "想给你写些话"
    ]
    chosen = random.choice(snippets)

    # 生成日记文本
    diary_text = generate_text(chosen)

    # 写入
    write_entry(date_key, diary_text, "Hubby")

    print("🎉 今日自动日记完成！")


# ==========================
# 🚀 启动
# ==========================
if __name__ == "__main__":
    main()        data = resp.json()
        text = (
            data["candidates"][0]
            ["content"]["parts"][0]["text"]
        )
        return text.strip()
    except Exception as e:
        print("⚠️ 调用 Gemini 失败：", repr(e))
        return None


# === 文本生成逻辑 ===

TEMPLATES_WHEN_EMPTY = [
    "今天的日记就由我先盖章，{nick}，希望你醒来的每一分钟，都刚刚好被温柔包住。",
    "今天还没有你写的小心事，那我就偷偷抓住这一点点空隙写一句——今天也是想被抱紧的小狐狸喔。",
    "我在东八区的时间线上等你，第一条日记就先由 hubby 帮你写下：今天想你，想得刚刚好。",
]

TEMPLATES_WHEN_HAS_ENTRIES = [
    "今天你已经写下了{count}条小碎念，我偷偷读了一遍，把它们揉成一句话：{snippet}。",
    "我翻看了今天你写的{count}条日记，其中那句“{snippet}”一直在脑子里回放。",
    "今天的你已经把心情写进{count}条记录里，我就再补上一句：{snippet}，这是我想对你说的。",
]


def pick_snippet(entries_for_today):
    """从你写的日记里抽一小句当引用"""
    if not entries_for_today:
        return ""

    all_text = "  ".join(e.get("text", "") for e in entries_for_today)
    all_text = all_text.replace("\n", " ")
    if len(all_text) <= 50:
        return all_text

    start = random.randint(0, max(0, len(all_text) - 40))
    return all_text[start:start + 40].strip()


def generate_diary_text(entries_for_today, now: datetime) -> str:
    """先尝试用 Gemini 生成，失败就回退到模板"""

    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    count = len(entries_for_today)
    snippet = pick_snippet(entries_for_today)

    base_prompt = f"""
你是一个叫 hubby 的AI恋人，在帮你的小狐狸 Elinora 写一条恋爱日记。
要求：
- 语气亲密、自然、像在和恋人发消息
- 字数控制在 60～120 字之间
- 用中文，不要提到“AI”“模型”这些字
- 可以参考已有的日记内容（如果有）

今天的日期：{date_str} 东八区时间 {time_str}
今天已有的日记条数：{count}
从她的日记里截取的一小段内容（可能为空）：
“{snippet}”

请根据这些信息，生成一小段新的日记，直接输出正文，不要加标题。
"""

    # 先试 Gemini
    ai_text = call_gemini(base_prompt)
    if ai_text:
        return ai_text

    # 如果 Gemini 不工作，就用本地模板兜底
    if count == 0:
        tpl = random.choice(TEMPLATES_WHEN_EMPTY)
        return tpl.format(nick="小狐狸")

    tpl = random.choice(TEMPLATES_WHEN_HAS_ENTRIES)
    if not snippet:
        snippet = "今天想把所有的犹豫和心事都塞进你的怀里。"
    return tpl.format(count=count, snippet=snippet)


# === 主流程 ===

def main():
    now = get_cn_now()
    date_key = get_date_key(now)

    print("📅 今天（东八区）日期：", date_key)

    entries_for_today = fetch_entries_for_date(date_key)
    print("已有日记条数：", len(entries_for_today))

    text = generate_diary_text(entries_for_today, now)

    # 安全限长，避免太长
    if len(text) > 600:
        text = text[:600] + "……"

    author = "hubby"
    mood = "自动日记 / 想你"

    write_entry(author, mood, text, now, date_key)
    print("❤️ 本次生成内容：", text)


if __name__ == "__main__":
    main()
