
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

SOURCE_URL = "https://starto.jp/s/p/live?ima=2112"
OUTPUT_FILE = "data/events.json"


class EventLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            href = attrs.get("href", "")
            if re.search(r"/s/p/live/\d+", href):
                self.current = {
                    "url": urljoin(SOURCE_URL, href),
                    "text": ""
                }

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            item = self.current
            item["text"] = " ".join(item["text"].split())
            if item["text"]:
                self.links.append(item)
            self.current = None


def main():
    request = Request(
        SOURCE_URL,
        headers={"User-Agent": "mileSixTONES-fan-project/1.0"}
    )

    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = EventLinkParser()
    parser.feed(html)

    # 同じ詳細ページの重複を除く
    unique = {}
    for item in parser.links:
        unique[item["url"]] = item

    events = []
    for item in unique.values():
        text = item["text"]

        date_match = re.search(
            r"\d{4}\.\d{2}\.\d{2}\s*-\s*"
            r"\d{4}\.\d{2}\.\d{2}",
            text
        )

        events.append({
            "event": text,
            "artist": "",
            "venue": "",
            "dateRange": date_match.group(0) if date_match else "",
            "url": item["url"],
            "source": SOURCE_URL
        })

    if not events:
        raise RuntimeError(
            "公演リンクを取得できませんでした。"
            "公式サイトのページ構造やアクセス制限を確認してください。"
        )

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_URL,
        "events": events
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"取得した公演リンク数: {len(events)}")


if __name__ == "__main__":
    main()
