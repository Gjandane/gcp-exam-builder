"""Run doc checks, the fixture test suite and the app tests from any working directory."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r'^\s*(`{3,}|~{3,})')
PLACEHOLDER = re.compile(r'<[a-z][\w .-]*>')
IMPORT_STEPS = '.claude/skills/exam-bank/templates/import-steps.txt'
README_CSV_PATH = ('export/<slug>-questions.csv', 'exam-bank/pmle/export/pmle-questions.csv')


def prose_lines(text):
    """Yield (line number, line) outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def bare_placeholders(name, text):
    """A `<placeholder>` outside code renders as an empty HTML tag on GitHub."""
    failures = []
    for number, line in prose_lines(text):
        for hit in PLACEHOLDER.findall(re.sub(r'`[^`]*`', '', line)):
            failures.append(f'{name}:{number}: put {hit} in backticks; GitHub hides it as an HTML tag')
    return failures


def fenced_import_steps(text):
    """Every fenced block that starts with the import-steps title, as a list of lines."""
    blocks = re.findall(r'(?m)^\s*`{3,}[^\n]*\n(Import into the sheet:\n.*?)\n\s*`{3,}', text.replace('\r\n', '\n'), re.S)
    return [block.split('\n') for block in blocks]


def check_import_steps(root):
    """The import steps are one text kept in five places; each copy must equal the template."""
    template = root / IMPORT_STEPS
    if not template.is_file():
        return []
    want = template.read_text(encoding='utf-8').strip().splitlines()
    copies = {
        'docs/specs/0001-exam-bank-skill.md': want,
        'docs/specs/0002-study-app.md': want,
        'README.md': [line.replace(*README_CSV_PATH) for line in want],
    }
    failures = []
    for name, expected in copies.items():
        path = root / name
        if not path.is_file():
            continue
        blocks = fenced_import_steps(path.read_text(encoding='utf-8'))
        if blocks != [expected]:
            failures.append(f'{name}: import steps must appear once, equal to {IMPORT_STEPS}')
    server = root / 'app/server/server.js'
    if server.is_file():
        array = re.search(r'IMPORT_STEPS_ = \[(.*?)\]\.join', server.read_text(encoding='utf-8'), re.S)
        lines = re.findall(r"^\s*'(.*)',\s*$", array[1], re.M) if array else []
        if lines != want:
            failures.append(f'app/server/server.js: IMPORT_STEPS_ must equal {IMPORT_STEPS}')
    return failures


def heading_ids(text):
    """GitHub-style heading anchors, including duplicate-heading suffixes."""
    anchors = set()
    for _, line in prose_lines(text):
        heading = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?\s*$', line)
        if heading is None:
            continue
        title = re.sub(r'<[^>]+>', '', heading[1]).lower()
        base = re.sub(r'[^\w\- ]', '', title).replace(' ', '-')
        anchor, suffix = base, 0
        while anchor in anchors:
            suffix += 1
            anchor = f'{base}-{suffix}'
        anchors.add(anchor)
    return anchors


def check_readme(root):
    """Return actionable failures for local links and skill-owned README rules."""
    readme = root / 'README.md'
    text = readme.read_text(encoding='utf-8')
    failures = []
    for match in re.finditer(r'\]\(([^)]+)\)', text):
        destination = urlsplit(match[1])
        if destination.scheme or destination.netloc:
            continue
        path = root / unquote(destination.path) if destination.path else readme
        line = text.count('\n', 0, match.start()) + 1
        if not path.is_file():
            failures.append(f'README.md:{line}: missing link target {match[1]}')
        elif destination.fragment and unquote(destination.fragment) not in heading_ids(path.read_text(encoding='utf-8')):
            failures.append(f'README.md:{line}: missing heading {match[1]}')
    config_path = root / '.claude/skills/exam-bank/templates/exams/pmle.example.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    for source in config.get('curated_sites', []) + config.get('llm_sources', []):
        if source['name'].casefold() in text.casefold():
            failures.append(f'README.md: question-site name {source["name"]!r}; link to config instead')
    if '\u2014' in text:
        failures.append('README.md: rewrite the sentence containing an em dash')
    if re.search(r'"permissions"\s*:', text):
        failures.append('README.md: link to setup instead of copying its permissions block')
    return failures + bare_placeholders('README.md', text)


def check_docs(root):
    """README rules, bare placeholders in the specs, and the import-steps copies."""
    failures = check_readme(root)
    for spec in sorted((root / 'docs/specs').glob('*.md')):
        failures += bare_placeholders(spec.relative_to(root).as_posix(), spec.read_text(encoding='utf-8'))
    return failures + check_import_steps(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--readme-only', action='store_true', help='run the doc checks only')
    args = parser.parse_args()
    failures = check_docs(ROOT)
    if failures:
        print('\n'.join(failures), file=sys.stderr, flush=True)
        return 1
    print('Doc checks passed.', flush=True)
    if args.readme_only:
        return 0
    # Inherit output streams so progress remains visible while tests run.
    pytest = subprocess.run([sys.executable, '-m', 'pytest'], cwd=ROOT).returncode
    npm = shutil.which('npm')
    if npm is None:
        print('npm not found: install Node 22 or newer to run the app tests.', file=sys.stderr, flush=True)
        return 1
    app = subprocess.run([npm, 'test'], cwd=ROOT / 'app').returncode
    return pytest or app


if __name__ == '__main__':
    raise SystemExit(main())
