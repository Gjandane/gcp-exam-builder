"""Step 3, fetch part: download each enabled llm_sources page and save HTML, text and meta."""

import hashlib
import urllib.parse

import store

MAX_TEXT = 150_000
TIMEOUT = 30


def page_dir(folder, name):
    return folder / 'raw' / name


def meta_path(folder, name, number):
    return page_dir(folder, name) / f'{number:02d}.meta.json'


def pages(config):
    """Yield (source entry, 1-based position, url) for every page of an enabled source."""
    for source in config.get('llm_sources') or []:
        if source.get('enabled'):
            for number, url in enumerate(source.get('urls') or [], 1):
                yield source, number, url


def page_text(html):
    from scrapers import common
    soup = common.soup(html)
    for tag in soup(['script', 'style', 'noscript', 'template']):
        tag.decompose()
    return common.cell_text(soup.body or soup)


def decode(answer):
    """UTF-8 first. requests guesses Latin-1 when the header names no charset."""
    try:
        return answer.content.decode('utf-8')
    except (AttributeError, UnicodeDecodeError):
        return answer.text


def _robots(get, cache, url):
    from scrapers import common
    parts = urllib.parse.urlsplit(url)
    origin = f'{parts.scheme}://{parts.netloc}'
    if origin not in cache:
        try:
            answer = get(origin + '/robots.txt', headers={'User-Agent': common.USER_AGENT}, timeout=TIMEOUT)
            cache[origin] = '' if answer.status_code == 404 else (
                answer.text if answer.status_code == 200 else None)
        except Exception:
            cache[origin] = None
    text = cache[origin]
    return text is not None and common.robots_allows(text, url)


def _save(folder, name, number, url, html, text, now):
    base = page_dir(folder, name) / f'{number:02d}'
    store.write_atomic(base.with_suffix('.html'), html.encode('utf-8'))
    store.write_atomic(base.with_suffix('.txt'), text.encode('utf-8'))
    return {'url': url, 'fetched_at': now,
            'sha256_txt': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'status': 'ok'}


def fetch_page(folder, name, number, url, now, get, cache):
    """Fetch one page and write its meta file. Return the meta."""
    from scrapers import common
    path = meta_path(folder, name, number)
    old = store.read_json(path, {})
    if not _robots(get, cache, url):
        meta = {'url': url, 'fetched_at': now, 'sha256_txt': '', 'status': 'failed: robots'}
    else:
        try:
            answer = get(url, headers={'User-Agent': common.USER_AGENT}, timeout=TIMEOUT)
        except Exception as error:
            meta = {'url': url, 'fetched_at': now, 'sha256_txt': '',
                    'status': f'failed: network {type(error).__name__}'}
        else:
            if answer.status_code != 200:
                meta = {'url': url, 'fetched_at': now, 'sha256_txt': '',
                        'status': f'failed: http {answer.status_code}'}
            else:
                html = decode(answer)
                text = page_text(html)
                meta = _save(folder, name, number, url, html, text, now)
                if len(text) > MAX_TEXT:
                    meta['status'] = 'failed: too large'
                elif (old.get('sha256_txt') == meta['sha256_txt'] and old.get('applied')
                      and old.get('status') in ('ok', 'done-partial')):
                    return old       # unchanged and already has a valid result
    store.write_atomic(path, store.dump_json(meta))
    return meta


def run(root, exam, now, get=None, config=None):
    if get is None:
        import requests
        get = requests.get
    config = config or store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    cache, lines = {}, []
    for source, number, url in pages(config):
        meta = fetch_page(folder, source['name'], number, url, now, get, cache)
        lines.append(f'{source["name"]} {number:02d}: {meta["status"]}')
    return '\n'.join(lines) or 'fetch: no enabled llm_sources page'
