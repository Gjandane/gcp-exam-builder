"""Untrusted worker result files and per-question validation."""
import json
import re
from urllib.parse import urlsplit


def cell_text(text):
    if not isinstance(text, str):
        return False
    outside = re.sub(r'`[^`]*`', '', text, flags=re.DOTALL)
    return not (re.search(r'<\s*/?\s*[A-Za-z][^>]*>', outside)
                or '](' in outside or re.search(r'^\s*#', outside, re.MULTILINE)
                or '**' in outside)


def doc_host(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        return (parsed.scheme == 'https' and not parsed.username and not parsed.password
                and (host == 'cloud.google.com' or host.endswith('.cloud.google.com')))
    except ValueError:
        return False


def doc_links(text):
    urls = re.findall(r'\b[a-z][a-z0-9+.-]*://[^\s`<>]+', text, re.IGNORECASE)
    return all(doc_host(url.rstrip('.,;:!?)')) for url in urls)


def preserves_user_ticks(row):
    return (row.get('answer_by') == 'user' and not any(
        source.get('name') == 'given' and source.get('unsure')
        for source in row.get('sources', [])))


def answers(result, row):
    if result.get('status') == 'unusable':
        reason = result.get('reason')
        return '' if isinstance(reason, str) and reason.strip() else 'unusable needs a reason.'
    if result.get('status') != 'ok':
        return 'Unknown answer status.'
    choices = {c['letter']: c for c in row['choices']}
    answer = result.get('answer')
    if (not isinstance(answer, list) or not answer or
            any(not isinstance(x, str) or x not in choices for x in answer) or
            len(set(answer)) != len(answer)):
        return 'Invalid answer letters.'
    words = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
    number_word = ('zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
                   'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|'
                   'thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand')
    match = re.search(r'\b(?:choose|select)\s+(\d+|(?:' + number_word +
                      r')(?:[ -](?:' + number_word + r'))*)\b', row['question'], re.I)
    if match:
        number = match[1].lower()
        if len(answer) != (int(number) if number.isdigit() else words.get(number, -1)):
            return 'Answer count does not match question.'
    if result.get('confidence') not in ('high', 'medium', 'low'):
        return 'Invalid confidence.'
    note = result.get('note')
    if not isinstance(note, str) or '\n' in note or '\r' in note:
        return 'Note must be one line.'
    if not doc_links(note):
        return 'Invalid documentation link.'
    error = explanation_error(result, choices)
    if error:
        return error
    explanations = result['explanations']
    conflicts = result.get('why_conflicts')
    if (not isinstance(conflicts, list) or any(not isinstance(x, str) or x not in choices
            or choices[x].get('explanation_by') != 'user' for x in conflicts)):
        return 'Invalid Why conflicts.'
    preserve_ticks = preserves_user_ticks(row)
    if preserve_ticks and sorted(answer) != sorted(row.get('answer', [])):
        return ''
    for letter, choice in choices.items():
        changed = sorted(answer) != sorted(row.get('answer', []))
        text = (choice.get('explanation', '') if choice.get('explanation_by') == 'user'
                else explanations.get(letter, '' if changed else choice.get('explanation', '')))
        if not isinstance(text, str) or not text.strip():
            return 'Every choice needs a valid explanation.'
    return ''


def explanation_error(result, choices):
    """Shared by answers and explanations: refs host, explanation keys and text."""
    refs = result.get('refs')
    if not isinstance(refs, list) or not all(doc_host(ref) for ref in refs):
        return 'Invalid documentation reference.'
    explanations = result.get('explanations')
    if not isinstance(explanations, dict) or any(k not in choices for k in explanations):
        return 'Invalid explanations.'
    if any(not cell_text(value) for key, value in explanations.items()
           if choices[key].get('explanation_by') != 'user'):
        return 'Invalid explanation text.'
    for key, value in explanations.items():
        if choices[key].get('explanation_by') == 'user':
            continue
        if not doc_links(value):
            return 'Invalid documentation link.'
    return ''


def explanations(result, row):
    if result.get('status') not in ('ok', 'doubt'):
        return 'Unknown explanations status.'
    choices = {c['letter']: c for c in row['choices']}
    error = explanation_error(result, choices)
    if error:
        return error
    for letter, choice in choices.items():
        if choice.get('explanation'):
            continue
        text = result['explanations'].get(letter)
        if not isinstance(text, str) or not text.strip():
            return 'Every choice needs a valid explanation.'
    if result['status'] == 'doubt':
        reason = result.get('reason')
        if not isinstance(reason, str) or not reason.strip():
            return 'doubt needs a reason.'
        if not cell_text(reason) or not doc_links(reason):
            return 'Invalid doubt reason.'
    return ''


def result_file(path, entry, step):
    """Return attributable evidence, result envelope, and any file error."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return False, None, 'Missing or unreadable result file.'
    if not isinstance(data, dict):
        return False, None, 'Result must be a JSON object.'
    if data.get('batch_id') != entry['batch_id'] or data.get('step') != step:
        return False, None, 'Result batch_id or step does not match the manifest.'
    if not isinstance(data.get('results'), list):
        return False, None, 'Result must contain a results list.'
    return True, data, ''


def tag(result, config):
    if result.get('status') == 'unusable':
        reason = result.get('reason')
        return '' if isinstance(reason, str) and reason.strip() else 'unusable needs a reason.'
    if result.get('status') != 'ok':
        return 'Unknown tag status.'
    numbers = {sub['number'] for section in config['sections'] for sub in section['subdomains']}
    subdomain = result.get('subdomain')
    if not isinstance(subdomain, str) or subdomain not in numbers:
        return 'Subdomain is not in the exam config.'
    if result.get('confidence') not in ('high', 'medium', 'low'):
        return 'Confidence must be high, medium or low.'
    if 'alt' in result:
        alt = result['alt']
        if not isinstance(alt, str) or alt not in numbers or alt == subdomain:
            return 'alt must be a different Subdomain in the exam config.'
    return ''


def questions(entry, data, error, check, config):
    """Reject duplicates and omissions independently; extra IDs never touch the bank."""
    accepted, rejected = {}, {}
    groups = {item: [] for item in entry['items']}
    if data is not None:
        for result in data['results']:
            if isinstance(result, dict) and isinstance(result.get('id'), str) and result['id'] in groups:
                groups[result['id']].append(result)
    for item, candidates in groups.items():
        reason = error
        if not reason:
            if len(candidates) != 1:
                reason = 'Missing question result.' if not candidates else 'Duplicate question ID.'
            else:
                reason = check(candidates[0], config)
        if reason:
            rejected[item] = reason
        else:
            accepted[item] = candidates[0]
    return accepted, rejected
