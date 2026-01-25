import argparse
import json
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests
from newspaper import Article

def google_news_rss_url(topic:str, lang='en', country='ZA') -> str:
    """Generate Google news RSS feed URL for a given topic."""
    q = quote_plus(topic)
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"

def fetch_rss_feed(url: str, limit: int = 30):
    feed = feedparser.parse(url)
    entries = feed.entries[:limit]
    out = []
    for e in entries:
        out.append({
            'title': e.title,
            'link': e.link,
            'published': e.published,
            'summary': e.summary
        })
    return out

def extract_article_content(url:str, timeout: int = 5, user_agent: str = 'Mozilla/5.0'):
    """uses newspaper3k to download and parse article content from a URL. 
       Some sites block scraping, we handle gracegully."""
    headers = {'User-Agent': user_agent}
    r = requests.get(url, headers = headers, timeout = timeout, allow_redirects = True)
    r.raise_for_status()

    a = Article(url, language = 'en')
    a.set_html(r.text)
    a.parse()
    return {
        'final_url': r.url,
        'text': a.text,
        'authors': a.authors,
        'publish_date': a.publish_date,
        'top_image': a.top_image
    }


def main():
    parser = argparse.ArgumentParser(description = 'Collect news articles on given topic.')
    parser.add_argument('--topic', required = True, help = 'topic query, e.g. "AI regulation in South Africa"')
    parser.add_argument('--limit', type=int, default=25, help="How many RSS items to process?")
    parser.add_argument('--country', default='ZA', help = 'Country code for Google News (default: ZA)')
    parser.add_argument('--lang', default='en', help = 'language code (hl/ceid), e.g. en)')
    parser.add_argument('--sleep', type = int, default = 1.0, help = 'Seconds to sleep between article fetches.')
    parser.add_argument('--out', default= 'articles.jsonl', help = 'Output file (json or csv)')
    args = parser.parse_args()

    rss_url = google_news_rss_url(args.topic, lang=args.lang, country=args.country)
    entries = fetch_rss_feed(rss_url, limit=args.limit)

    results = []
    for i,e in enumerate(entries):
        link = e.get('link')
        if not link:
            continue

        row = {**e, 'topic': args.topic, 'collected_at': datetime.utcnow().isoformat()}
        try:
            extracted = extract_article_content(link)
            row.update(extracted)
            row['ok'] = True
        except Exception as ex:
            row['ok'] = False
            row['error'] = str(ex)

        results.append(row)
        print(f"[{i}/{len(entries)}] {'Ok' if row['ok'] else 'Fail'} - {row.get('title')}")
        time.sleep(args.sleep)

    if args.out.lower().endswith(".cvs"):
        pd.DataFrame(results).to_csv(args.out, index = False)
    else:
        with open(args.out, 'w', encoding = 'utf-8') as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(results)} rows to {args.out}")
    print("Tip: filter ok = True to keep only successfully extracted articles.")

if __name__ == "__main__":
    main()