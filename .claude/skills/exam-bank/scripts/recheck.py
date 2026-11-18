"""Report re-check: read the newest Reports CSV and decide which questions it makes pending."""
import csv
import datetime
import io

import store

COLUMNS = ('report_id', 'reported_at', 'question_id', 'note', 'question_updated_at',
           'status', 'resolved_at', 'resolution')


def newest_csv(folder):
    files = sorted((folder / 'reports').glob('*.csv'), key=lambda p: (p.stat().st_mtime, p.name))
    if not files:
        raise store.Stop(
            f'No Reports CSV in {(folder / "reports").as_posix()}. In the sheet open the Reports tab, '
            'File > Download > Comma-separated values, save it there, then rerun recheck.')
    return files[-1]


def read_reports(path):
    """Open and unresolved Report rows, by header name."""
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as error:
        raise store.Stop(f'Cannot read {path.as_posix()}: {error}') from error
    reader = csv.DictReader(io.StringIO(text, newline=''))
    missing = [name for name in COLUMNS if name not in (reader.fieldnames or [])]
    if missing:
        raise store.Stop(f'{path.name} lacks columns: {", ".join(missing)}. '
                         'Download the Reports tab, not another tab.')
    return [{name: (row.get(name) or '').strip() for name in COLUMNS} for row in reader
            if (row.get('status') or '').strip().lower() == 'open']


def _moment(text):
    try:
        value = datetime.datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def later(reported_at, rechecked_at):
    """True when the Report postdates the last re-check. An empty `rechecked_at` is before everything."""
    if not rechecked_at:
        return True
    a, b = _moment(reported_at), _moment(rechecked_at)
    return a > b if a and b else reported_at > rechecked_at


def plan(folder, rows):
    """Return the CSV path, open Reports by question ID, and skipped (question ID, reason) pairs."""
    path = newest_csv(folder)
    by_id = {row['id']: row for row in rows}
    reports, skipped = {}, []
    for report in read_reports(path):
        question = by_id.get(report['question_id'])
        if question is None or question.get('status') != 'active':
            entry = (report['question_id'], 'unknown' if question is None else 'retired')
            if entry not in skipped:
                skipped.append(entry)
            continue
        reports.setdefault(question['id'], []).append(report)
    return path, reports, skipped
