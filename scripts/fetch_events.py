import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin

# コンサート / ステージ / イベント の3ページを取得
SOURCES = [
    ("concert", "https://starto.jp/s/p/live?ct=concert"),
    ("stage", "https://starto.jp/s/p/live?ct=stage"),
    ("event", "https://starto.jp/s/p/live?ct=event"),
]
OUTPUT_FILE = "data/events.json"

# 例: 「タイトル 2026.12.12 - 2027.01.12 CONCERTタイトル アーティスト」
PATTERN = re.compile(
    r"^(?P<title>.+?)\s+"
    r"(?P<date>\d{4}\.\d{2}\.\d{2}(?:\s*-\s*\d{4}\.\d{2}\.\d{2})?)\s+"
    r"(?P<cat>CONCERT|STAGE|EVENT)"
    r"(?P<rest>.*)$"
)


class EventLinkParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "") or ""
            if re.search(r"/s/p/live/\d+", href):
                self.current = {"url": urljoin(self.base_url, href), "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["text"] = " ".join(self.current["text"].split())
            if self.current["text"]:
                self.links.append(self.current)
            self.current = None


def clean_url(url):
    # ima=... や artist= などの計測用パラメータを外して、詳細ページのURLを統一
    return url.split("?")[0]


def parse_item(item, source_url, category):
    text = item["text"]
    m = PATTERN.match(text)
    if not m:
        return {
            "event": text,
            "artist": "",
            "venue": "",
            "dateRange": "",
            "category": category,
            "url": clean_url(item["url"]),
            "source": source_url,
        }

    title = m.group("title").strip()
    rest = m.group("rest").strip()
    # CATEGORYの直後にタイトルが繰り返されるので取り除くと、残りがアーティスト名
    if rest.startswith(title):
        rest = rest[len(title):].strip()

    return {
        "event": title,
        "artist": rest,
        "venue": "",  # 会場は詳細ページにあるので、必要なら次のステップで追加
        "dateRange": re.sub(r"\s+", " ", m.group("date")),
        "category": category,
        "url": clean_url(item["url"]),
        "source": source_url,
    }


def fetch(url):
    req = Request(url, headers={"User-Agent": "mileSixTONES-fan-project/1.0"})
    with urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def main():
    events = {}
    for category, url in SOURCES:
        try:
            parser = EventLinkParser(url)
            parser.feed(fetch(url))
        except Exception as e:
            print(f"[skip] {category}: {e}")
            continue

        for link in parser.links:
            ev = parse_item(link, url, category)
            events[ev["url"]] = ev
        print(f"{category}: {len(parser.links)} links")
        time.sleep(1)  # 相手サイトに負荷をかけない

    if not events:
        raise RuntimeError("公演リンクを取得できませんでした。ページ構造やアクセス制限を確認してください。")

    event_list = list(events.values())

    # 内容が前回と同じなら書き込まない(毎回コミットされるのを防ぐ)
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            if json.load(f).get("events") == event_list:
                print("変更なし")
                return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "https://starto.jp/s/p/live",
        "events": event_list,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"保存: {len(event_list)}件")


if __name__ == "__main__":
    main()
