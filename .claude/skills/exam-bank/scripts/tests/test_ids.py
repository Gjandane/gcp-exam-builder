"""Golden norm and question ID vectors. ADR 0001 freezes these for good.

Expected values are hand-written literals. Each ID was computed once with
hashlib over the literal hash input in the comment, not through `ids`.
Never edit a vector to make a test pass.
"""

import pytest

import ids

NORM_QUESTION = [
    ("Which  TWO steps\treduce\n skew? ", "which two steps reduce skew"),
    ("ﬁne Straße", "fine strasse"),                    # NFKC ligature, casefold
    ("ＡＢＣ　１２３", "abc 123"),    # full-width
    ("A. Which one?", "a which one"),                             # no prefix strip on a question
    ("snake_case-name `gcloud config` a+b=c $5 50%",
     "snakecasename gcloud config a+b=c $5 50"),
    ("“quoted” — it’s", "quoted its"),
    ("a - b", "a b"),
]

NORM_CHOICE = [
    ("A. Use Dataflow", "use dataflow"),
    ("(b) Use Dataproc", "use dataproc"),
    ("c: x", "x"),
    ("d) y", "y"),
    ("  F.  z", "z"),
    ("g. z", "g z"),                  # g is outside a-f
    ("a good plan", "a good plan"),   # no delimiter
    ("A.text", "atext"),              # no space after the delimiter
    ("A. B. two", "b two"),           # one prefix only
]


@pytest.mark.parametrize("text,expected", NORM_QUESTION)
def test_norm_question(text, expected):
    assert ids.norm(text) == expected


@pytest.mark.parametrize("text,expected", NORM_CHOICE)
def test_norm_choice(text, expected):
    assert ids.norm(text, choice=True) == expected


def test_id_simple():
    # "what is 2+2\n3\n4"
    assert ids.question_id("What is 2+2?", ["4", "3"]) == "q_62f355254e47"


def test_id_reordered_choices_pair_gives_one_id():
    # "which service runs apache beam pipelines\ncloud composer\ndataflow\ndataproc"
    first = ids.question_id(
        "Which service runs Apache Beam pipelines?",
        ["A. Dataflow", "B. Dataproc", "C. Cloud Composer"])
    second = ids.question_id(
        "which service runs  Apache Beam pipelines",
        ["Cloud Composer", "dataproc", "DATAFLOW."])
    assert first == second == "q_1692a2271270"


def test_id_sorts_choices_by_code_point():
    # "pick one\nalpha\nzeta\närger"
    assert ids.question_id("Pick one", ["Zeta", "Ärger", "alpha"]) == "q_2246d48882b5"
