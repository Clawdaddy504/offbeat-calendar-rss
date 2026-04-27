#!/usr/bin/env python3
import argparse, json, urllib.request, xml.sax.saxutils as sax
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape
from pathlib import Path
import re

LIST_URL = 'https://calendar.offbeat.com/events.json?calendar_id=76&calendar_view_id=80'
EVENT_JSON = 'https://calendar.offbeat.com/events/{id}.json'
EVENT_HTML = 'https://calendar.offbeat.com/calendars/all-events/{id}'


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def strip_html(s):
    if not s:
        return ''
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</p\s*>', '\n\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return unescape(s).strip()


def iso_to_rfc822(s):
    if not s:
        return format_datetime(datetime.now(timezone.utc))
    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    return format_datetime(dt)


def build_items(limit):
    listing = fetch_json(LIST_URL)
    events = listing.get('events', [])[:limit]
    items = []
    for e in events:
        event_id = e['id']
        detail = fetch_json(EVENT_JSON.format(id=event_id))
        title = detail.get('summary') or detail.get('name') or f'Event {event_id}'
        venue = (detail.get('venue') or {}).get('name') or (e.get('venue') or {}).get('name') or ''
        start = detail.get('starttime') or e.get('starttime')
        end = detail.get('endtime') or e.get('endtime')
        desc = strip_html(detail.get('description') or '')
        moreinfo = detail.get('moreinfo') or ''
        ticketurl = detail.get('ticketurl') or ''
        cats = detail.get('categories') or e.get('categories') or []
        cat_text = ', '.join(str(c.get('name') or c.get('id')) for c in cats)
        html_url = EVENT_HTML.format(id=event_id)
        parts = []
        if venue:
            parts.append(f'Venue: {venue}')
        if start:
            parts.append(f'Starts: {start}')
        if end:
            parts.append(f'Ends: {end}')
        if cat_text:
            parts.append(f'Categories: {cat_text}')
        if moreinfo:
            parts.append(f'More info: {moreinfo}')
        if ticketurl:
            parts.append(f'Tickets: {ticketurl}')
        if desc:
            parts.append('')
            parts.append(desc)
        description = '\n'.join(parts).strip()
        items.append({
            'id': f'offbeat-event-{event_id}',
            'source': 'offbeat',
            'title': title,
            'venue': venue,
            'start': start,
            'end': end,
            'categories': [c.get('name') or c.get('id') for c in cats],
            'moreinfo': moreinfo,
            'ticket_url': ticketurl,
            'event_url': html_url,
            'description': description,
            'pubDate': iso_to_rfc822(detail.get('updated_at') or detail.get('created_at') or start),
        })
    return items


def write_rss(out_path, items):
    now = format_datetime(datetime.now(timezone.utc))
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>']
    rss.append('<title>OffBeat All Events Calendar</title>')
    rss.append('<link>https://calendar.offbeat.com/calendars/all-events</link>')
    rss.append('<description>Unofficial RSS feed for OffBeat Magazine\'s All Events calendar.</description>')
    rss.append(f'<lastBuildDate>{sax.escape(now)}</lastBuildDate>')
    for item in items:
        rss.append('<item>')
        rss.append(f'<title>{sax.escape(item["title"])}</title>')
        rss.append(f'<link>{sax.escape(item["event_url"])}</link>')
        rss.append(f'<guid isPermaLink="false">{sax.escape(item["id"])}</guid>')
        rss.append(f'<pubDate>{sax.escape(item["pubDate"])}</pubDate>')
        rss.append(f'<description>{sax.escape(item["description"])}</description>')
        rss.append('</item>')
    rss.append('</channel></rss>')
    Path(out_path).write_text('\n'.join(rss), encoding='utf-8')


def write_json(out_path, items):
    json_path = Path(out_path).with_name('events.json')
    payload = {
        'source': 'offbeat',
        'source_url': 'https://calendar.offbeat.com/calendars/all-events',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'count': len(items),
        'events': items,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return json_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=200)
    args = ap.parse_args()

    items = build_items(args.limit)
    write_rss(args.out, items)
    json_path = write_json(args.out, items)
    print(f'Wrote {len(items)} items to {args.out}')
    print(f'Wrote {len(items)} items to {json_path}')

if __name__ == '__main__':
    main()
