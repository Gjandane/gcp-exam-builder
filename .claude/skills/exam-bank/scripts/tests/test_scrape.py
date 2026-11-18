import json
import pathlib

import pytest

import merge
import scrape
import state
import store
from scrapers import common, examtopics

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "examtopics"
BASE = "https://www.examtopics.com/exams/google/professional-machine-learning-engineer/view/"
SITE = {"name": "examtopics", "url": BASE, "enabled": True}
PAGE = (FIXTURES / "page-1.html").read_text(encoding="utf-8")
GATE = (FIXTURES / "gate.html").read_text(encoding="utf-8")
ROBOTS = "User-agent: *\nDisallow: /login/\nDisallow: /user/\n"


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds

    def monotonic(self):
        return self.t


class FakeSession:
    """Pages by URL. `on_poll(n)` may change what the open window shows."""

    def __init__(self, pages, on_poll=None, robots=(200, ROBOTS)):
        self.pages = dict(pages)
        self.current = ""
        self.on_poll = on_poll
        self.polls = 0
        self.loads = []
        self.robots = robots

    def get_text(self, url):
        return self.robots

    def load(self, url):
        self.loads.append(url)
        self.current = url
        return self.pages[url]

    def snapshot(self):
        self.polls += 1
        if self.on_poll:
            self.on_poll(self)
        return self.pages[self.current]

    def url(self):
        return self.current


def numbered(html, page_total=3):
    return html.replace("out of 38 pages", f"out of {page_total} pages")


def pages(total=3, gated=()):
    out = {}
    for n in range(1, total + 1):
        out[examtopics.page_url(BASE, n)] = GATE if n in gated else numbered(PAGE, total)
    return out


def run(root, session, clock=None, **kw):
    clock = clock or FakeClock()
    return common.run_site(root, "pmle", SITE, examtopics, session, sleep=clock.sleep,
                           clock=clock.monotonic, pause=lambda: 4.5,
                           now=lambda: "2026-11-17T09:00:00Z", **kw), clock


def folder(root):
    return store.exam_dir(root, "pmle")


def test_every_page_is_saved_with_raw_html_records_and_progress(root):
    lines, clock = run(root, FakeSession(pages(3)))
    f = folder(root)
    assert lines == ["examtopics: 3 page(s) saved, 3/3 done"]
    for n in (1, 2, 3):
        assert (f / "raw/examtopics" / f"page-{n}.html").is_file()
    rows = store.read_jsonl(f / "sources/examtopics.jsonl")
    assert len(rows) == 15   # five valid questions on each of three pages
    assert {r["sources"][0]["url"] for r in rows} == {examtopics.page_url(BASE, n) for n in (1, 2, 3)}
    assert store.read_json(f / "sources/examtopics.progress.json") == {
        "pages_done": 3, "pages_total": 3, "last_run": "2026-11-17T09:00:00Z"}
    assert clock.sleeps == [4.5, 4.5]   # one pause between pages, none after the last


def test_skipped_questions_are_logged_by_source_and_reason(root):
    run(root, FakeSession(pages(1)))
    events = store.read_jsonl(folder(root) / "log.jsonl")
    assert [(e["kind"], e["source"], e["ref"].rsplit("#", 1)[1], e["reason"]) for e in events] == [
        ("skipped", "examtopics", "5", "needs an image"),
        ("skipped", "examtopics", "6", "7 choices, need 2 to 6"),
        ("skipped", "examtopics", "8", "1 choices, need 2 to 6")]


def test_rerun_continues_from_the_last_saved_page(root):
    session = FakeSession(pages(3, gated=(3,)))
    clock = FakeClock()
    lines, _ = run(root, session, clock)
    assert lines[0].startswith("examtopics: waiting on user")   # timed out on page 3
    assert store.read_json(folder(root) / "sources/examtopics.progress.json")["pages_done"] == 2
    session2 = FakeSession(pages(3))
    lines, _ = run(root, session2)
    assert session2.loads == [examtopics.page_url(BASE, 3)]
    assert lines == ["examtopics: 1 page(s) saved, 3/3 done"]
    assert len(store.read_jsonl(folder(root) / "sources/examtopics.jsonl")) == 15


def test_resaving_a_page_replaces_its_records(root):
    f = folder(root)
    common.save_page(root, "pmle", "examtopics", examtopics, BASE, 1, 3, numbered(PAGE, 3), "t1")
    common.save_page(root, "pmle", "examtopics", examtopics, BASE, 1, 3, numbered(PAGE, 3), "t2")
    rows = store.read_jsonl(f / "sources/examtopics.jsonl")
    assert len(rows) == 5
    assert {r["sources"][0]["scraped_at"] for r in rows} == {"t2"}


def test_gate_with_the_exact_action_goes_into_the_state_file(root):
    seen = {}

    def on_poll(session):
        seen["gates"] = store.read_json(folder(root) / "state.json")["gates"]
        session.pages[session.current] = numbered(PAGE, 2)   # the user logged in

    session = FakeSession(pages(2, gated=(2,)), on_poll=on_poll)
    lines, clock = run(root, session)
    action = "Log in to examtopics in the open browser window, then rerun /exam-bank pmle scrape"
    assert seen["gates"] == {"examtopics": action}
    # Cards appeared, so the gate cleared and the page was saved.
    assert store.read_json(folder(root) / "state.json")["gates"] == {}
    assert lines == ["examtopics: 2 page(s) saved, 2/2 done"]
    assert session.polls == 1
    assert clock.sleeps == [4.5, common.POLL_SECONDS]


def test_gate_times_out_after_eight_minutes_and_stays_set(root):
    session = FakeSession(pages(2, gated=(2,)))
    lines, clock = run(root, session)
    action = "Log in to examtopics in the open browser window, then rerun /exam-bank pmle scrape"
    assert lines[0] == f"examtopics: waiting on user: {action}"
    assert session.polls == 96   # every 5 seconds for 8 minutes
    assert store.read_json(folder(root) / "state.json")["gates"] == {"examtopics": action}
    assert store.read_json(folder(root) / "sources/examtopics.progress.json")["pages_done"] == 1


def test_polling_never_navigates_while_the_user_is_on_a_login_page(root):
    def on_poll(session):
        session.current = "https://www.examtopics.com/login/"
        session.pages[session.current] = GATE

    session = FakeSession(pages(2, gated=(2,)), on_poll=on_poll)
    session.pages["https://www.examtopics.com/login/"] = GATE
    run(root, session)
    assert session.loads == [examtopics.page_url(BASE, 1), examtopics.page_url(BASE, 2)]


def test_user_who_lands_elsewhere_after_login_is_sent_back_to_the_page(root):
    target = examtopics.page_url(BASE, 2)

    def on_poll(session):
        if session.polls == 1:
            session.current = "https://www.examtopics.com/"
            session.pages[session.current] = GATE
        session.pages[target] = numbered(PAGE, 2)

    session = FakeSession(pages(2, gated=(2,)), on_poll=on_poll)
    lines, _ = run(root, session)
    assert session.polls == 2   # off the gate for two polls before the window is taken back
    assert session.loads == [examtopics.page_url(BASE, 1), target, target]
    assert lines == ["examtopics: 2 page(s) saved, 2/2 done"]


def test_a_load_error_is_logged_as_a_failed_page_and_stops(root):
    class Broken(FakeSession):
        def load(self, url):
            if url.endswith("/2/"):
                raise TimeoutError("page.goto timed out")
            return super().load(url)

    with pytest.raises(store.Stop, match="page 2 failed to load"):
        run(root, Broken(pages(3)))
    events = store.read_jsonl(folder(root) / "log.jsonl")
    assert [e["kind"] for e in events if e["kind"] == "failed_page"] == ["failed_page"]
    assert store.read_json(folder(root) / "sources/examtopics.progress.json")["pages_done"] == 1


PAYWALL_HTML = ('<html><body><nav>Plans</nav><article><div class="access-plan plan-pro">'
                '<button>Choose a plan</button></div></article></body></html>')
LOGIN = "https://www.examtopics.com/login/"


def test_paywall_page_ends_the_source_without_a_gate_or_a_wait(root):
    session = FakeSession(pages(3) | {examtopics.page_url(BASE, 3): PAYWALL_HTML})
    lines, clock = run(root, session)
    assert lines[0].startswith("examtopics: paywall at page 3")
    assert session.polls == 0   # no 8 minute wait
    f = folder(root)
    assert not (f / "state.json").exists() or store.read_json(f / "state.json").get("gates", {}) == {}
    assert not (f / "raw/examtopics/page-3.html").exists()
    assert store.read_json(f / "sources/examtopics.progress.json") == {
        "pages_done": 2, "pages_total": 3, "last_run": "2026-11-17T09:00:00Z", "paywall_page": 3}
    assert [e["kind"] for e in store.read_jsonl(f / "log.jsonl") if e["kind"] == "paywall"] == ["paywall"]


def test_state_counts_a_paywalled_source_as_done(root):
    run(root, FakeSession(pages(3) | {examtopics.page_url(BASE, 3): PAYWALL_HTML}))
    text = state.run(root, "pmle", "2026-11-17T09:10:00Z")
    assert "| examtopics | curated | done: paywall at page 3 | 2/3 | 10 |" in text
    assert "waiting on user" not in text


def test_a_rerun_that_gets_past_the_paywall_drops_the_marker(root):
    run(root, FakeSession(pages(3) | {examtopics.page_url(BASE, 3): PAYWALL_HTML}))
    run(root, FakeSession(pages(3)))
    assert store.read_json(folder(root) / "sources/examtopics.progress.json") == {
        "pages_done": 3, "pages_total": 3, "last_run": "2026-11-17T09:00:00Z"}


def test_an_aborted_load_that_lands_on_the_paywall_is_a_paywall(root):
    target = examtopics.page_url(BASE, 2)

    class Aborts(FakeSession):
        def load(self, url):
            if url == target:
                self.current = url
                self.pages[url] = PAYWALL_HTML
                raise RuntimeError("net::ERR_ABORTED")
            return super().load(url)

    lines, _ = run(root, Aborts(pages(2)))
    assert lines[0].startswith("examtopics: paywall at page 2")


def test_an_aborted_load_that_lands_on_a_login_page_waits_for_the_user(root):
    target = examtopics.page_url(BASE, 2)

    class Aborts(FakeSession):
        def load(self, url):
            if url == target and not self.pages.get("logged_in"):
                self.current = LOGIN
                raise RuntimeError("net::ERR_ABORTED")
            return super().load(url)

    session = Aborts(pages(2) | {LOGIN: GATE})
    lines, _ = run(root, session)
    assert lines[0].startswith("examtopics: waiting on user")
    assert session.polls == 97   # one snapshot after the abort, then every 5 seconds for 8 minutes


def test_an_abort_that_leaves_the_previous_page_showing_is_never_saved_as_this_page(root):
    target = examtopics.page_url(BASE, 2)

    class Aborts(FakeSession):
        def load(self, url):
            if url == target:
                raise RuntimeError("net::ERR_ABORTED")   # the window still shows page 1
            return super().load(url)

    with pytest.raises(store.Stop, match="page 2 failed to load.*window shows .*view/"):
        run(root, Aborts(pages(2)))
    assert store.read_json(folder(root) / "sources/examtopics.progress.json")["pages_done"] == 1


def test_login_that_ends_on_the_paywall_stops_the_wait(root):
    target = examtopics.page_url(BASE, 2)

    def on_poll(session):
        session.pages[session.current] = PAYWALL_HTML   # the user logged in and sees the upsell

    session = FakeSession(pages(2, gated=(2,)), on_poll=on_poll)
    lines, _ = run(root, session)
    assert lines[0].startswith("examtopics: paywall at page 2")
    assert session.polls == 1
    assert store.read_json(folder(root) / "state.json")["gates"] == {}


def test_a_gate_on_page_one_is_a_gate_too(root):
    session = FakeSession(pages(1, gated=(1,)))
    lines, _ = run(root, session)
    assert lines[0].startswith("examtopics: waiting on user")
    assert not (folder(root) / "sources/examtopics.progress.json").exists()


def test_gate_write_keeps_other_state_keys(root):
    path = folder(root) / "state.json"
    path.write_bytes(store.dump_json({"merged": {"sources/x.jsonl": "abc"}, "setup": {"passed_at": "t"}}))
    common.set_gate(root, "pmle", "examtopics", "act")
    common.set_gate(root, "pmle", "other", "act2")
    common.set_gate(root, "pmle", "examtopics", None)
    assert store.read_json(path) == {"merged": {"sources/x.jsonl": "abc"},
                                     "setup": {"passed_at": "t"}, "gates": {"other": "act2"}}


def test_missing_page_count_line_stops(root):
    session = FakeSession({BASE: PAGE.replace("Viewing page 1 out of 38 pages.", "")})
    with pytest.raises(store.Stop, match="page count"):
        run(root, session)


# robots.txt

def test_robots_disallow_stops_before_any_fetch(root):
    robots = (200, f"User-agent: *\nDisallow: {examtopics.page_url(BASE, 2).split('.com')[1]}\n")
    with pytest.raises(store.Stop, match="disallows"):
        common.check_robots(FakeSession({}, robots=robots), "examtopics",
                            [examtopics.page_url(BASE, n) for n in (1, 2)])


def test_robots_allow_the_view_pages_and_a_missing_file_allows_all():
    urls = [examtopics.page_url(BASE, n) for n in (1, 2)]
    common.check_robots(FakeSession({}), "examtopics", urls)
    common.check_robots(FakeSession({}, robots=(404, "")), "examtopics", urls)


def test_unreadable_robots_stops_rather_than_guessing():
    with pytest.raises(store.Stop, match="robots.txt answered 403"):
        common.check_robots(FakeSession({}, robots=(403, "")), "examtopics", [BASE])


# the command

class ScriptedOpen:
    def __init__(self, session):
        self.session = session
        self.profiles = []

    def __call__(self, profile):
        self.profiles.append(profile)
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


def only_examtopics(root):
    path = root / "exam-bank" / "config" / "exams" / "pmle.yaml"
    text = path.read_text(encoding="utf-8")
    old = "  - name: certsafari" + "\n    url:"
    head, tail = text.split(old, 1)
    tail = tail.replace("enabled: true", "enabled: false", 1)
    path.write_text(head + old + tail, encoding="utf-8")


def test_command_runs_each_enabled_site_with_its_own_profile_and_skips_a_site_without_scraper(root):
    path = root / "exam-bank" / "config" / "exams" / "pmle.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "name: certsafari", "name: nosuchsite", 1), encoding="utf-8")
    opener = ScriptedOpen(FakeSession(pages(1)))
    out = scrape.run(root, "pmle", "now", open_session=opener)
    assert "nosuchsite: no scraper yet, skipped" in out
    assert "examtopics: 1 page(s) saved" in out
    assert opener.profiles == [root / "exam-bank" / ".browser" / "examtopics"]


def test_command_skips_a_site_with_no_pages_left(root):
    only_examtopics(root)
    opener = ScriptedOpen(FakeSession(pages(1)))
    scrape.run(root, "pmle", "now", open_session=opener)
    out = scrape.run(root, "pmle", "now", open_session=opener)
    assert "examtopics" not in out
    assert len(opener.profiles) == 1


# state table and merge

def test_state_table_shows_pages_done_over_total_and_the_gate_action(root):
    run(root, FakeSession(pages(3, gated=(3,))))
    text = state.run(root, "pmle", "2026-11-17T09:10:00Z")
    action = "Log in to examtopics in the open browser window, then rerun /exam-bank pmle scrape"
    assert f"| examtopics | curated | waiting on user: {action} | 2/3 | 10 |" in text
    assert "- scrape: waiting on user" in text


def test_scraped_records_merge_with_site_and_community_answers(root):
    run(root, FakeSession(pages(1)))
    merge.run(root, "pmle", "2026-11-17T09:20:00Z")
    rows = store.read_jsonl(folder(root) / "bank.jsonl")
    assert len(rows) == 5
    by_question = {r["question"].split("\n")[0]: r for r in rows}
    second = by_question["Your card fraud model must answer within 40 ms, but feature joins take most of that time. Which change helps most?"]
    record = second["sources"][0]
    assert (record["name"], record["site_answer"], record["community_answer"]) == (
        "examtopics", ["C"], ["D"])
    assert record["source_question_no"] == "2"
    assert second["uncertain"] is True   # site and community answers differ
    third = by_question["A research group wants every training run's learning rate, batch size and loss side by side. Which tool fits?"]
    assert third["sources"][0]["site_answer"] == ["B"]
    assert third["sources"][0]["community_answer"] == []
    assert third["uncertain"] is False
    assert json.dumps(rows)  # plain JSON
