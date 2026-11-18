import pathlib

import pytest

import merge
import scrape
import store
from scrapers import certsafari
from scrapers.http import HttpSession

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "certsafari"
URL = "https://www.certsafari.com/google/machine-learning-engineer-professional/practice-questions"
PAGE = (FIXTURES / "practice-questions.html").read_text(encoding="utf-8")
ROBOTS = "User-agent: *\nAllow: /\nDisallow: /*/quiz/\n"


def by_number():
    return {r["number"]: r for r in certsafari.parse_page(PAGE, URL)}


def test_parse_page_returns_position_stem_choices_answer_explanations_and_label():
    assert by_number()[1] == {
        "number": 1,
        "stem": ("A team logs click data to a table named `web_clicks` and wants churn predictions "
                 "without writing model code. What should they use?"),
        "choices": ["A custom training job on GPUs", "BigQuery ML with a logistic regression model",
                    "A self-managed Kubeflow cluster"],
        "site_answer": ["B"],
        "explanations": ["Incorrect. Custom training adds code the team wants to avoid.",
                         "Correct. BigQuery ML trains in SQL where the data already lives.",
                         "Incorrect. Running Kubeflow yourself adds upkeep."],
        "subdomain_label": "Subdomain 1.1: Choosing managed training tools.",
    }


def test_multi_answer_line_gives_every_letter_and_the_select_count_span_is_not_stem():
    second = by_number()[2]
    assert second["site_answer"] == ["A", "C"]
    assert second["stem"].endswith("(Select two)")
    assert "(Select 2)" not in second["stem"]
    assert len(second["explanations"]) == 5


def test_a_choice_without_an_explanation_gets_an_empty_one_and_a_bare_label_is_kept_raw():
    third = by_number()[3]
    assert third["explanations"] == ["", "Correct. Drift explains a quiet drop in quality."]
    assert third["subdomain_label"] == "2.1: Watching models for drift."


def test_image_choice_count_and_missing_answer_are_skipped_with_a_reason():
    records, skipped = certsafari.parse(PAGE, URL)
    assert [r["number"] for r in records] == [1, 2, 3]
    assert skipped == [{"number": 4, "reason": "needs an image"},
                       {"number": 5, "reason": "7 choices, need 2 to 6"},
                       {"number": 6, "reason": "no answer line"}]


def test_the_page_is_one_page_and_a_page_without_cards_has_no_count():
    assert certsafari.page_url(URL, 1) == URL
    assert certsafari.page_count(PAGE) == 1
    assert certsafari.page_count("<html><body>Verifying you are human</body></html>") is None


class HttpFake(HttpSession):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages

    def get_text(self, url):
        return (200, ROBOTS) if url.endswith("/robots.txt") else (200, self.pages[url])


class Opener:
    def __init__(self, session):
        self.session = session

    def __call__(self, profile):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


@pytest.fixture
def only_certsafari(root):
    path = root / "exam-bank" / "config" / "exams" / "pmle.yaml"
    text = path.read_text(encoding="utf-8")
    old = "enabled: true\n    answers_trusted: true\n  - name: certsafari"
    assert old in text
    path.write_text(text.replace(old, "enabled: false\n    answers_trusted: true\n  - name: certsafari", 1),
                    encoding="utf-8")
    return root


def scrape_page(root, page=PAGE):
    return scrape.run(root, "pmle", "2026-11-17T10:00:00Z", open_session=Opener(HttpFake({URL: page})))


def test_scrape_saves_raw_rows_progress_and_logs_skips(only_certsafari):
    root = only_certsafari
    assert scrape_page(root) == "certsafari: 1 page(s) saved, 1/1 done"
    folder = store.exam_dir(root, "pmle")
    assert (folder / "raw/certsafari/page-1.html").read_text(encoding="utf-8") == PAGE
    rows = store.read_jsonl(folder / "sources/certsafari.jsonl")
    assert [r["sources"][0]["source_question_no"] for r in rows] == ["1", "2", "3"]
    assert store.read_json(folder / "sources/certsafari.progress.json") == {
        "pages_done": 1, "pages_total": 1, "last_run": "2026-11-17T10:00:00Z"}
    events = store.read_jsonl(folder / "log.jsonl")
    assert [(e["source"], e["ref"].rsplit("#", 1)[1], e["reason"]) for e in events] == [
        ("certsafari", "4", "needs an image"), ("certsafari", "5", "7 choices, need 2 to 6"),
        ("certsafari", "6", "no answer line")]
    assert scrape.run(root, "pmle", "later", open_session=Opener(HttpFake({}))).startswith("scrape: no")


def test_merge_gives_source_explanations_and_no_tag_when_the_label_is_not_in_the_config(only_certsafari):
    root = only_certsafari
    scrape_page(root)
    merge.run(root, "pmle", "2026-11-17T10:05:00Z")
    rows = store.read_jsonl(store.exam_dir(root, "pmle") / "bank.jsonl")
    assert len(rows) == 3
    first = next(r for r in rows if r["question"].startswith("A team logs click data"))
    assert [c["explanation_by"] for c in first["choices"]] == ["source"] * 3
    assert first["choices"][1]["explanation"] == "Correct. BigQuery ML trains in SQL where the data already lives."
    assert first["answer"] == ["B"] and first["answer_by"] == "source"
    assert first["sources"][0]["name"] == "certsafari"
    assert first["subdomain"] == "" and first["subdomain_by"] == ""


def test_a_label_matching_the_config_sets_subdomain_by_source(only_certsafari):
    root = only_certsafari
    scrape_page(root, PAGE.replace("Subdomain 1.1: Choosing managed training tools.", "Subdomain 4.1: Serving models"))
    merge.run(root, "pmle", "2026-11-17T10:05:00Z")
    rows = store.read_jsonl(store.exam_dir(root, "pmle") / "bank.jsonl")
    tagged = [r for r in rows if r["subdomain"] == "4.1"]
    assert len(tagged) == 1 and tagged[0]["subdomain_by"] == "source"
    assert tagged[0]["choices"][1]["explanation_by"] == "source"


def test_certsafari_uses_plain_http_and_a_page_without_cards_stops_instead_of_polling(only_certsafari):
    assert scrape._session_class(certsafari) is HttpSession
    with pytest.raises(store.Stop, match="no question cards"):
        scrape_page(only_certsafari, "<html></html>")
    folder = store.exam_dir(only_certsafari, "pmle")
    assert not (folder / "sources/certsafari.progress.json").exists()
