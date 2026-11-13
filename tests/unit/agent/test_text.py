"""agent/text.py: <thinking>...</thinking> never reaches the customer, even split across chunks."""

import pytest

from agent.text import ThinkingFilter


def run(chunks):
    f = ThinkingFilter()
    return "".join(f.feed(c) for c in chunks) + f.flush()


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (["Hello ", "there"], "Hello there"),
        (["<thinking>find veg</thinking>Here are 3 dishes"], "Here are 3 dishes"),
        (["<think", "ing>plan", " more</thin", "king>Done"], "Done"),
        (["A <thinking>x</thinking>B<thinking>y</thinking>C"], "A BC"),
        (["price < 20 SAR"], "price < 20 SAR"),
        (["ends with <"], "ends with <"),  # a lone '<' at the end is text
        (["<thinking>never closed"], ""),
        (["مرحبا <thinking>x</thinking>بك"], "مرحبا بك"),
    ],
)
def test_filter(chunks, expected):
    assert run(chunks) == expected


def test_text_streams_without_waiting_for_the_end():
    f = ThinkingFilter()
    assert f.feed("Hello ") == "Hello "
    assert f.feed("<thi") == ""  # might be a tag: held back
    assert f.feed("s is text") == "<this is text"


from agent.text import BLOCKED_MARKER, MarkerFilter  # noqa: E402


@pytest.mark.parametrize(
    "chunks, text, seen",
    [
        (["Hello"], "Hello", False),
        ([BLOCKED_MARKER], "", True),
        (["[SUMAAT_", "BLOCKED]"], "", True),
        (["ok [", "x]"], "ok [x]", False),  # a '[' that turns out not to be the marker is kept
        (["Hi " + BLOCKED_MARKER], "Hi ", True),
    ],
)
def test_marker_filter(chunks, text, seen):
    f = MarkerFilter()
    out = "".join(f.feed(c) for c in chunks) + f.flush()
    assert (out, f.seen) == (text, seen)


from agent.text import MarkdownFilter  # noqa: E402


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (["Try **Kleija** now"], "Try Kleija now"),
        (["Try *", "*Kleija*", "* now"], "Try Kleija now"),  # ** split across chunks
        (["## Options\n- a\n# b"], "Options\n- a\nb"),
        (["gluten_free and 2 * 3"], "gluten_free and 2 * 3"),  # single * and _ stay
        (["price #1 ", "## not a heading"], "price #1 ## not a heading"),  # only at a line start
        (["ends with *"], "ends with *"),
    ],
)
def test_markdown_filter(chunks, expected):
    f = MarkdownFilter()
    assert "".join(f.feed(c) for c in chunks) + f.flush() == expected


def test_markdown_bold_split_right_after_the_marks():
    f = MarkdownFilter()
    out = f.feed("- **") + f.feed("تيراميسو - 24 ريال\n- مهلبية**") + f.feed(" - 15") + f.flush()
    assert out == "- تيراميسو - 24 ريال\n- مهلبية - 15"
