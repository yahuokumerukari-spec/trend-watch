"""
AI×データの観察日記 スクリプト

毎日、
1. 市場・トレンドの兆し(はてなブックマーク テクノロジー人気エントリー)
2. SNS/世の中の不満・ニーズの兆し(はてなブックマーク 暮らし・世の中 人気エントリー)
3. 興味分野(AI・プログラミング)の動き(Googleニュース検索)
を集めて、Geminiに「ビジネスの種になりそうな兆し」を意識して整理させ、
- リポジトリの data/YYYY-MM-DD.md に保存(蓄積用ログ)
- Discordに要約版を通知
する。

必要な環境変数(GitHub Actionsの「Secrets」に設定します):
- GEMINI_API_KEY : Google AI StudioでもらったAPIキー
- DISCORD_WEBHOOK_URL : Discordのウェブフックの URL
"""

import os
import sys
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# --- 設定 ---------------------------------------------------------------
SOURCES = {
    "市場・トレンド": "https://b.hatena.ne.jp/hotentry/it.rss",
    "SNS・世の中の不満やニーズ": "https://b.hatena.ne.jp/hotentry/life.rss",
    "興味分野(AI・プログラミング)の動き": "https://news.google.com/rss/search?q=AI%20ツール%20OR%20生成AI&hl=ja&gl=JP&ceid=JP:ja",
}
MAX_PER_SOURCE = 10
GEMINI_MODEL = "gemini-3.5-flash"
JST = timezone(timedelta(hours=9))


def get_articles() -> dict:
    result = {}
    for label, url in SOURCES.items():
        feed = feedparser.parse(url)
        titles = [entry.title for entry in feed.entries[:MAX_PER_SOURCE]]
        result[label] = titles
    return result


def build_prompt(articles: dict, date_str: str) -> str:
    blocks = []
    for label, titles in articles.items():
        joined = "\n".join(f"- {t}" for t in titles) or "(取得できませんでした)"
        blocks.append(f"■{label}\n{joined}")
    source_text = "\n\n".join(blocks)

    return (
        f"あなたは新規事業の種を探しているアナリストです。{date_str}時点の以下の情報をもとに、"
        "『観察日記』を作成してください。\n\n"
        "出力形式(Markdown、この構成を厳守):\n"
        "## 市場・トレンドの兆し\n"
        "(2〜4個、箇条書き。それぞれ「何が起きているか」＋「なぜ注目か」を1〜2文で)\n\n"
        "## 人々の不満・ニーズの兆し\n"
        "(2〜4個、箇条書き。潜在的な『困りごと』『欲しいもの』を推測して言語化する)\n\n"
        "## 興味分野(AI・プログラミング)の動き\n"
        "(2〜4個、箇条書き。技術・ツール・市場の動きを整理)\n\n"
        "## 今日のビジネスの種メモ\n"
        "(上記を踏まえて、事業アイデアのタネになりそうな仮説を1〜2個、短く)\n\n"
        "前置き・締めの挨拶は不要。この4見出し以外は出力しないこと。\n\n"
        f"{source_text}"
    )


def call_gemini(prompt: str, api_key: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Geminiの応答を解析できませんでした: {data}") from exc


def save_log(date_str: str, content: str) -> str:
    os.makedirs("data", exist_ok=True)
    path = f"data/{date_str}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 観察日記 {date_str}\n\n{content}\n")
    return path


def send_to_discord(date_str: str, content: str, webhook_url: str) -> None:
    message = f"🔭 **観察日記 {date_str}**\n\n{content}"
    chunks = [message[i:i + 1900] for i in range(0, len(message), 1900)] or [message]
    for chunk in chunks:
        response = requests.post(webhook_url, json={"content": chunk}, timeout=30)
        response.raise_for_status()


def main() -> None:
    gemini_key = os.environ.get("GEMINI_API_KEY")
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")

    if not gemini_key or not discord_webhook:
        print("環境変数 GEMINI_API_KEY / DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    articles = get_articles()
    prompt = build_prompt(articles, date_str)
    content = call_gemini(prompt, gemini_key)

    path = save_log(date_str, content)
    print(f"ログを保存しました: {path}")

    send_to_discord(date_str, content, discord_webhook)
    print("Discordへの送信が完了しました")


if __name__ == "__main__":
    main()
