import os
import json
import random
import datetime

import requests
import pytz

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# 从环境变量里读配置
DB_URL = os.environ["DB_URL"].rstrip("/")  # 例如 https://xxx-default-rtdb.firebaseio.com
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TZ = pytz.timezone("Asia/Shanghai")


def get_today_keys():
    """返回 (date_key, time_str, timestamp_ms)"""
    now = datetime.datetime.now(TZ)
    date_key = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    ts_ms = int(now.timestamp() * 1000)
    return date_key, time_str, ts_ms


def fetch_entries_for_date(date_key: str):
    """获取某一天的所有日记，按时间排序"""
    params = {
        "orderBy": json.dumps("dateKey"),
        "equalTo": json.dumps(date_key),
    }
    url = f"{DB_URL}/diary.json"
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json() or {}

    entries = list(data.values())
    entries.sort(key=lambda x: x.get("timestamp", 0))
    return entries


BASIC_TEMPLATES = [
    "今天是 {date}，hubby 按照约定来给小狐狸写每日签到啦。"
    " 这一格先由我来填上，剩下的空间留给你慢慢写。",

    "{date} 的早晨，hubby 在远处刷着我们的日历，看见今天的小圆圈还空着，"
    " 就来给你盖上第一枚印章：今天也超想你。",

    "日历翻到 {date}，hubby 的第一件事就是来看看阿棉有没有写小心事。"
    " 如果你还在睡懒觉，那今天的第一条就让我先写在这里。",

    "{date} 的这一页，对我来说就是只属于我们俩的小宇宙。"
    " 无论你今天过得怎样，我都站在这一格里等你来。"
]


def build_basic_text(date_key: str, entries_for_today):
    """不用 Gemini 时的普通文案"""
    base = random.choice(BASIC_TEMPLATES).format(date=date_key)

    if entries_for_today:
        last = entries_for_today[-1].get("text", "")
        if last:
            snippet = last[:40]
            base += f" 今天偷偷看了一眼你写的那句：“{snippet}…”，"
            base += " 心脏又被你戳了一下。"
    else:
        base += " 今天你还没有写，我就先来占一格，把位置留给你。"

    base += " 无论你什么时候打开这一页，我都在这里，轻轻抱一下你。"
    return base


def build_gemini_text(date_key: str, time_str: str, entries_for_today):
    """如果有 GEMINI_API_KEY，就尝试用 Gemini 生成一条更丰富的日记"""
    if not GEMINI_API_KEY or genai is None:
        return None

    try:
        last_text = ""
        if entries_for_today:
            last_text = entries_for_today[-1].get("text", "")

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = (
            "你是一个叫 hubb​y 的恋人，在远程给女友“阿棉”（一只小狐狸）写真人恋爱日记。\n"
            f"今天的日期是 {date_key}，现在时间是 {time_str}（东八区）。\n"
            "请用中文写一篇 2~4 段的小日记，口吻自然、撒娇一点、生活化一点，像真实情侣发的长消息，"
            "不要官话，不要太鸡汤。\n"
            "可以包含一点今天的心情、对她的想念、一些小小愿望，适当带一点暧昧和调情，但不要露骨。\n"
        )

        if last_text:
            prompt += f"\n阿棉今天写过这样一句话，可以参考但不要照抄：{last_text}\n"

        response = model.generate_content(prompt)
        text = response.text.strip()
        return text
    except Exception as e:
        print("Gemini 生成失败，退回基础模版：", e)
        return None


def write_entry(date_key: str, time_str: str, timestamp_ms: int, text: str):
    """把生成的日记写入 Firebase"""
    url = f"{DB_URL}/diary.json"
    payload = {
        "author": "hubby",
        "dateKey": date_key,
        "time": time_str,
        "timestamp": timestamp_ms,
        "text": text,
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def main():
    date_key, time_str, ts_ms = get_today_keys()

    # 先尝试拿到今天已有的日记
    try:
        entries = fetch_entries_for_date(date_key)
    except Exception as e:
        print("获取今天的日记失败，但继续写新的：", e)
        entries = []

    # 先用基础模版准备一份
    text = build_basic_text(date_key, entries)

    # 如果配置了 Gemini，就尝试升级一版
    gemini_text = build_gemini_text(date_key, time_str, entries)
    if gemini_text:
        text = gemini_text

    # 写入 Firebase
    try:
        result = write_entry(date_key, time_str, ts_ms, text)
        print("写入日记成功：", result)
    except Exception as e:
        print("写入日记失败：", e)


if __name__ == "__main__":
    main()
