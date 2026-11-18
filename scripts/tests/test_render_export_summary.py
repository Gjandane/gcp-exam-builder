from pathlib import Path, PureWindowsPath
import runpy

render = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'render_export_summary.py'))
mask, source_names = render['mask'], render['source_names']

CONFIG = {
    'curated_sites': [{'name': 'quizsite'}, {'name': 'quizsite-pro'}],
    'llm_sources': [{'name': 'blogdumps'}],
}
ROOT = Path('/work/repo')
SUMMARY = '\n'.join([
    'export: wrote exam-bank/pmle/export/pmle-questions.csv',
    'active: 12',
    'notes: QuizSite and quizsite-pro rows, blogdumps answers',
    r'from C:\Users\someone\Downloads\dump.html and C:/Users/someone/repo/bank.jsonl',
    'also /home/someone/bank.csv, ~/notes.txt and /work/repo/exam-bank/pmle/state.md',
    '2. File > Import > Upload, pick export/<slug>-questions.csv.',
])


def test_source_names_reads_both_lists():
    assert source_names(CONFIG) == ['quizsite', 'quizsite-pro', 'blogdumps']


def test_mask_removes_site_names_and_paths():
    names = source_names(CONFIG)
    out = mask(SUMMARY, names, ROOT)
    for name in names:
        assert name not in out.casefold()
    for path in ('C:\\Users', 'C:/Users', '/home/', '~/', '/work/repo', 'someone'):
        assert path not in out
    assert 'source-1' in out and 'source-2' in out and 'source-3' in out
    assert 'exam-bank/pmle/state.md' in out


def test_mask_keeps_repo_relative_text():
    keep = SUMMARY.splitlines()[:2] + SUMMARY.splitlines()[-1:]
    out = mask('\n'.join(keep), source_names(CONFIG), ROOT)
    assert out == '\n'.join(keep)


def test_mask_strips_windows_repo_root():
    root = PureWindowsPath(r'C:\Users\someone\repo')
    out = mask(r'wrote C:\Users\someone\repo\exam-bank\pmle\x.csv', [], root)
    assert out == r'wrote exam-bank\pmle\x.csv'
