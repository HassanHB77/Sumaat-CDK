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
