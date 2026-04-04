import os
import re
import datetime
import feedparser
import json
from dotenv import load_dotenv

# 로컬 실행 시 .env 파일에서 API 키를 불러옵니다
load_dotenv()

from google import genai
from google.genai import types

# Setup Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

client = genai.Client(api_key=API_KEY)

def fetch_rss(url):
    try:
        feed = feedparser.parse(url)
        items = feed.entries[:10]  # Top 10 items
        text_content = ""
        for i, item in enumerate(items):
            desc = getattr(item, 'description', '') or getattr(item, 'summary', '')
            text_content += f"[{i+1}] Title: {item.title}\nDescription: {desc}\n\n"
        return text_content
    except Exception as e:
        print("RSS Fetch Error:", e)
        return "No news available."

def generate_content(news_text):
    prompt = f"""
You are an expert financial news editor. Based on the following latest news extracts, create a Korean summary for a "Daily Card News" webpage.
Output a JSON object with this EXACT structure (No markdown fences, no extra text):
{{
  "cards": [
    {{
      "theme_class": "card-war",
      "icon_class": "war-icon",
      "icon_emoji": "⚔️",
      "tag_class": "tag-war",
      "tag_text": "지정학 / 주요 이슈",
      "summary_num": "01 / 지정학",
      "summary_title": "뉴스 요약 제목",
      "article_title": "상세 기사 제목",
      "article_summary": "기사 본문 요약 (3~4문장)",
      "key_points": [
        "핵심 포인트 1",
        "핵심 포인트 2",
        "핵심 포인트 3"
      ],
      "advice_label": "💡 투자자 한 줄 전략",
      "advice_text": "투자 전략 코멘트"
    }}
  ]
}}
* `cards` must have exactly 3 items. Use `card-war`, `card-oil`, `card-bond` or similar thematic names for `theme_class`, `icon_class`, `tag_class`.

News Text:
{news_text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        print("Failed to parse JSON:", e)
        print("Raw Output:", response.text[:500])
        raise e

def render_html(data):
    summaries_html = ""
    for c in data.get("cards", []):
        summaries_html += f'<div class="summary-card {c["theme_class"]}">\n  <div class="card-num">{c["summary_num"]}</div>\n  <h3>{c["summary_title"]}</h3>\n</div>\n'
    
    news_html = ""
    for i, c in enumerate(data.get("cards", [])):
        points_html = ""
        for p in c.get("key_points", []):
            points_html += f'<li>{p}</li>\n'
            
        full_theme = c["theme_class"] if i == 0 else f'{c["theme_class"]}-full'
            
        news_html += f"""
    <article class="news-card {full_theme}" id="card-{i+1}">
      <div class="card-header">
        <div class="card-icon {c["icon_class"]}">{c["icon_emoji"]}</div>
        <div class="card-header-text">
          <span class="card-tag {c["tag_class"]}">{c["tag_text"]}</span>
          <h3>{c["article_title"]}</h3>
        </div>
      </div>
      <div class="card-body">
        <div class="card-divider"></div>
        <p class="card-summary">{c["article_summary"]}</p>
        <ul class="key-points">
          {points_html}
        </ul>
        <div class="advice-box">
          <div>
            <div class="advice-label">{c["advice_label"]}</div>
            <div class="advice-text">{c["advice_text"]}</div>
          </div>
        </div>
      </div>
    </article>
"""
    return summaries_html, news_html

def update_html(data):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, 'index.html')

    if not os.path.exists(html_path):
        print(f"Error: {html_path} not found.")
        exit(1)

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    date_str = kst_now.strftime("%Y.%m.%d")
    time_str = kst_now.strftime("%Y.%m.%d %H:%M KST")

    html = re.sub(r'<!-- DATE_START -->.*?<!-- DATE_END -->', f'<!-- DATE_START -->{date_str}<!-- DATE_END -->', html, flags=re.DOTALL)
    html = re.sub(r'<!-- TIME_START -->.*?<!-- TIME_END -->', f'<!-- TIME_START -->{time_str}<!-- TIME_END -->', html, flags=re.DOTALL)

    summaries_html, news_html = render_html(data)

    html = re.sub(r'<!-- SUMMARY_START -->.*?<!-- SUMMARY_END -->', f'<!-- SUMMARY_START -->\n{summaries_html}\n<!-- SUMMARY_END -->', html, flags=re.DOTALL)

    html = re.sub(r'<!-- NEWS_START -->.*?<!-- NEWS_END -->', f'<!-- NEWS_START -->\n{news_html}\n<!-- NEWS_END -->', html, flags=re.DOTALL)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print("index.html successfully updated!")

if __name__ == "__main__":
    rss_url = "https://investinglive.com/feed/news"
    print("Fetching RSS from:", rss_url)
    news_text = fetch_rss(rss_url)
    print(f"Fetched {news_text.count('[')} articles.")

    print("Generating content with Gemini...")
    data = generate_content(news_text)

    print("Updating HTML...")
    update_html(data)
    print("Done!")
