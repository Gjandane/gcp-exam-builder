import pathlib

from scrapers import examtopics

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "examtopics"
URL = "https://www.examtopics.com/exams/google/professional-machine-learning-engineer/view/"


def page1():
    return (FIXTURES / "page-1.html").read_text(encoding="utf-8")


def by_number():
    return {r["number"]: r for r in examtopics.parse_page(page1(), URL)}


def test_parse_page_returns_the_five_fields_per_question():
    first = by_number()[1]
    assert first == {
        "number": 1,
        "stem": "A bakery chain retrains its loaf demand model every night from a BigQuery table of till receipts.\nThe retrain must run with no one at the keyboard. What should you set up?",
        "choices": ["A scheduled Vertex AI Pipelines run & a BigQuery read step",
                    "A cron entry on a spare Compute Engine VM",
                    "An analyst who exports the receipts to CSV each evening",
                    "A notebook the night shift reruns by hand"],
        "site_answer": ["A"],
        "community_answer": ["A"],
    }


def test_choice_text_carries_no_letter_prefix_and_no_most_voted_label():
    for record in by_number().values():
        for text in record["choices"]:
            assert "Most Voted" not in text
            assert not text.startswith(("A.", "B.", "C.", "D."))


def test_community_answer_differs_from_site_answer_when_the_tag_sits_elsewhere():
    second = by_number()[2]
    assert second["site_answer"] == ["C"]
    assert second["community_answer"] == ["D"]


def test_question_without_most_voted_tag_has_empty_community_answer():
    third = by_number()[3]
    assert third["site_answer"] == ["B"]
    assert third["community_answer"] == []
    assert len(third["choices"]) == 3


def test_multi_answer_card_reads_the_community_line_since_no_option_is_tagged():
    # On the live site a multi-answer card prints "Correct Answer: AD" and tags no option.
    fourth = by_number()[4]
    assert fourth["site_answer"] == ["A", "C"]
    assert fourth["community_answer"] == ["A", "C"]


def test_code_is_stored_in_backticks():
    seventh = by_number()[7]
    assert seventh["stem"] == ("Jobs keep landing in the wrong region, so you open Cloud Shell and run "
                               "`gcloud config configurations list`.\n"
                               "```\ngcloud config get-value ai/region\necho \"region checked\"\n```")
    assert seventh["choices"][:2] == ["`gcloud auth application-default revoke`",
                                      "Set it once with `gcloud config set ai/region europe-west4`"]


def test_image_and_out_of_range_questions_are_skipped_with_a_reason():
    records, skipped = examtopics.parse(page1(), URL)
    assert sorted(r["number"] for r in records) == [1, 2, 3, 4, 7]
    assert skipped == [
        {"number": 5, "reason": "needs an image"},
        {"number": 6, "reason": "7 choices, need 2 to 6"},
        {"number": 8, "reason": "1 choices, need 2 to 6"},
    ]


def test_page_count_comes_from_the_viewing_line():
    assert examtopics.page_count(page1()) == 38


def test_cards_mean_no_gate_and_the_login_modal_alone_is_not_a_gate():
    gate = (FIXTURES / "gate.html").read_text(encoding="utf-8")
    assert examtopics.has_cards(page1())
    assert "login-modal" in page1()
    assert not examtopics.has_cards(gate)
    assert examtopics.page_count(gate) is None


def test_page_urls_follow_the_config_url():
    assert examtopics.page_url(URL, 1) == URL
    assert examtopics.page_url(URL, 2) == URL + "2/"
    assert examtopics.page_url(URL, 38) == URL + "38/"


def test_an_answer_line_that_is_not_just_letters_gives_no_site_answer():
    html = page1().replace('<strong class="ml-1">B</strong>', '<strong class="ml-1">See B Exhibit</strong>')
    third = {r["number"]: r for r in examtopics.parse_page(html, URL)}[3]
    assert third["site_answer"] == []
