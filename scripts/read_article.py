"""Read a supplied WeChat article without paid APIs. Python standard library only."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler


VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
BLOCK = {'p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'li', 'blockquote', 'tr', 'pre'}


def validate_url(value):
    p = urlsplit(value)
    if p.scheme != 'https' or p.hostname != 'mp.weixin.qq.com' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Only HTTPS mp.weixin.qq.com article URLs are accepted.')
    return value


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []
        self.title = []
        self.author = []
        self.images = []
        self.og_title = ''
        self.has_body = False

    def inside(self, name):
        return any(x[1] == name for x in self.stack)

    def hidden(self):
        return any(x[0] in ('script', 'style', 'noscript') for x in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and a.get('property') == 'og:title':
            self.og_title = a.get('content', '')
        if a.get('id') == 'js_content':
            self.has_body = True
        if tag not in VOID:
            self.stack.append((tag, a.get('id', '')))
        if self.inside('js_content') and not self.hidden():
            if tag in BLOCK or tag == 'br':
                self.text.append('\n')
            if tag == 'img':
                src = a.get('data-src') or a.get('src') or ''
                self.images.append({'position': len(self.images) + 1, 'url': src, 'alt': a.get('alt', '')})
                self.text.append('\n[图片 %d]\n' % len(self.images))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.inside('js_content') and tag in BLOCK and not self.hidden():
            self.text.append('\n')
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.hidden():
            return
        if self.inside('js_content'):
            self.text.append(data)
        if self.inside('activity-name'):
            self.title.append(data)
        if self.inside('js_name'):
            self.author.append(data)


def extract(html, url):
    p = ArticleParser()
    p.feed(html)
    text = re.sub(r'\n[ \t\r\u00a0]*\n+', '\n\n', ''.join(p.text)).strip()
    title = ''.join(p.title).strip() or p.og_title.strip()
    ok = p.has_body and bool(text) and bool(title)
    return {'status': 'ok' if ok else 'needs_browser', 'url': url, 'title': title,
            'author': ''.join(p.author).strip(), 'text': text, 'images': p.images,
            'text_length': len(text), 'sha256': hashlib.sha256(html.encode('utf-8')).hexdigest(),
            'limits': ['Images are indexed, not OCR-read.', 'Videos and comments are not extracted.'],
            'reason': None if ok else 'No validated article title and nonempty #js_content; may be a challenge or incomplete page.'}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--url', required=True)
    ap.add_argument('--html-file', type=Path)
    ap.add_argument('--output-dir', required=True, type=Path)
    args = ap.parse_args()
    try:
        validate_url(args.url)
        if args.output_dir.exists():
            raise ValueError('Output directory exists; choose a new directory.')
        if args.html_file:
            raw = args.html_file.read_bytes()
            html = raw.decode('utf-8-sig')
            final_url = args.url
        else:
            req = Request(args.url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-CN,zh;q=0.9'})
            with build_opener(SafeRedirect()).open(req, timeout=25) as response:
                final_url = validate_url(response.url)
                raw = response.read(12 * 1024 * 1024 + 1)
                if len(raw) > 12 * 1024 * 1024:
                    raise ValueError('Response exceeds 12 MiB; use browser reading.')
                html = raw.decode(response.headers.get_content_charset() or 'utf-8')
        result = extract(html, args.url)
        result.update(final_url=final_url, retrieved_at=datetime.now(timezone.utc).isoformat(),
                      source_kind='supplied_html' if args.html_file else 'direct_http',
                      raw_sha256=hashlib.sha256(raw).hexdigest(), paid_api_calls=0)
        args.output_dir.mkdir(parents=True)
        (args.output_dir / 'source.html').write_bytes(raw)
        (args.output_dir / 'article.txt').write_text(result['text'], encoding='utf-8')
        (args.output_dir / 'article.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: result[k] for k in ('status', 'title', 'text_length', 'reason', 'source_kind', 'paid_api_calls')}, ensure_ascii=False))
        return 0 if result['status'] == 'ok' else 2
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc), 'paid_api_calls': 0}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
