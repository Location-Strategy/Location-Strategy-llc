#!/usr/bin/env python3
"""
Regenerates the Chartbook section of index.html from the Location Strategy
Chartbook's public beehiiv RSS feed.

Run manually with:  python3 scripts/update_chartbook.py
Runs automatically via .github/workflows/update-chartbook.yml
"""
import datetime
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://rss.beehiiv.com/feeds/Fu4rQlaTm3.xml"
INDEX_HTML = "index.html"
NUM_POSTS = 3
EXCERPT_MAX_LEN = 200
START_MARKER = "<!-- CHARTBOOK_ITEMS:START -->"
END_MARKER = "<!-- CHARTBOOK_ITEMS:END -->"

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


def fetch_feed(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "location-strategy-chartbook-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    # Turn common block/line breaks into spaces before stripping remaining tags,
    # so words from adjacent tags don't get jammed together.
    fragment = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(fragment)
    return re.sub(r"\s+", " ", text).strip()


def extract_excerpt(content_html: str) -> str:
    """Pick the first substantial paragraph of body text as a preview excerpt."""
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", content_html, flags=re.IGNORECASE | re.DOTALL)
    for raw in paragraphs:
        text = strip_tags(raw)
        if len(text) >= 50:
            if len(text) > EXCERPT_MAX_LEN:
                truncated = text[:EXCERPT_MAX_LEN].rsplit(" ", 1)[0]
                text = truncated + "…"
            return text
    return "Read the latest edition of the Location Strategy Chartbook."


def parse_items(xml_text: str):
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        content_encoded = item.findtext(CONTENT_NS) or ""
        if not (title and link and pub_date_raw):
            continue
        try:
            from email.utils import parsedate_to_datetime
            pub_date = parsedate_to_datetime(pub_date_raw)
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "link": link,
                "pub_date": pub_date,
                "excerpt": extract_excerpt(content_encoded),
            }
        )
    items.sort(key=lambda i: i["pub_date"], reverse=True)
    return items[:NUM_POSTS]


def render_card(item: dict) -> str:
    pub_date = item["pub_date"]
    # e.g. "September 5, 2026" / "September 5 Edition" (matches the site's existing style)
    date_label = f"{pub_date.strftime('%B')} {pub_date.day}, {pub_date.year}"
    edition_label = f"{pub_date.strftime('%B')} {pub_date.day} Edition"
    excerpt = html.escape(item["excerpt"], quote=False)
    link = html.escape(item["link"], quote=True)

    return f"""  <a href="{link}"
     target="_blank"
     class="post-card">
    <span class="post-date">{date_label}</span>
    <h4>{edition_label}</h4>
    <p class="post-excerpt">
      {excerpt}
    </p>
    <span class="read-more">Read Full Analysis</span>
  </a>"""


def render_block(items: list) -> str:
    cards = "\n\n".join(render_card(item) for item in items)
    return f"{START_MARKER}\n\n{cards}\n\n  {END_MARKER}"


def splice_into_index(index_text: str, new_block: str) -> str:
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if not pattern.search(index_text):
        raise RuntimeError(
            f"Could not find {START_MARKER} ... {END_MARKER} markers in {INDEX_HTML}"
        )
    return pattern.sub(new_block, index_text, count=1)


def main() -> int:
    xml_text = fetch_feed(FEED_URL)
    items = parse_items(xml_text)
    if not items:
        print("No items parsed from feed; leaving index.html untouched.", file=sys.stderr)
        return 1

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        index_text = f.read()

    new_block = render_block(items)
    updated_text = splice_into_index(index_text, new_block)

    if updated_text == index_text:
        print("Chartbook section already up to date.")
        return 0

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(updated_text)

    print(f"Updated {INDEX_HTML} with {len(items)} latest chartbook post(s):")
    for item in items:
        print(f"  - {item['pub_date'].date()}  {item['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
