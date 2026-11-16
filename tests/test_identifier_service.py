"""Identifier generation: keyword extraction is ReDoS-safe and tag-aware."""

import time

import pytest

from app.extensions import db
from app.models.case import Case
from app.services.identifier_service import IdentifierService

# --- keyword extraction ----------------------------------------------------


@pytest.fixture()
def service():
    return IdentifierService()


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        ("roof leaking badly", "ROOF"),
        ("<p>roof leaking badly</p>", "ROOF"),
        ("<p><strong>roof</strong> leaking</p>", "ROOF"),
        ("a bc roof", "ROOF"),  # words under 4 characters are skipped
        ("<p>unclosed roof", "UNCLOSED"),  # an unclosed tag is not a word boundary problem
        ("&nbsp;roof", "ROOF"),
        ("damp-proofing", "DAMP"),
        ("extraordinarily long word", "EXTRAORDIN"),  # truncated to 10
    ],
)
def test_keyword_is_the_first_long_word(service, notes, expected):
    assert service._extract_keyword(notes, None) == expected


def test_tags_separate_words_rather_than_joining_them(service):
    """`<p>roof</p><p>leak</p>` must not collapse into the word "roofleak"."""
    assert service._extract_keyword("<p>roof</p><p>leak</p>", None) == "ROOF"


@pytest.mark.parametrize(
    "notes",
    ["", "   ", "<p></p>", "<p><br></p>", "<p>&nbsp;</p>", "123 456", "a bc", "<<<<"],
)
def test_notes_without_a_long_word_fall_back_to_interaction(service, notes):
    assert service._extract_keyword(notes, None) == "INTERACTION"


def test_transcript_is_used_when_there_are_no_notes(service):
    assert service._extract_keyword(None, "resident reported damp") == "RESIDENT"


def test_notes_take_precedence_over_the_transcript(service):
    assert service._extract_keyword("<p>roof</p>", "damp") == "ROOF"


def test_no_notes_and_no_transcript_falls_back_to_interaction(service):
    assert service._extract_keyword(None, None) == "INTERACTION"


# The previous implementation stripped tags with re.sub(r"<[^>]+>", " ", ...),
# which backtracks quadratically. CodeQL flagged it as py/polynomial-redos.
# These are the input shapes that trigger it.
ADVERSARIAL = [
    "<" * 500_000,
    "<a " * 150_000,
    "<p>" * 150_000,
    "<!--" * 120_000,
    "&" * 500_000,
    "<" + "a" * 500_000,
]


@pytest.mark.parametrize("payload", ADVERSARIAL, ids=lambda p: f"{p[:6]!r}x{len(p)}")
def test_adversarial_notes_are_processed_in_linear_time(service, payload):
    started = time.perf_counter()
    service._extract_keyword(payload, None)
    assert time.perf_counter() - started < 2.0


# --- location part ---------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("filled.count.soap", "FILLED"),
        ("extraordinary.count.soap", "EXTRAORD"),  # truncated to 8
        (None, "UNK"),
        ("", "UNK"),
    ],
)
def test_location_part_is_the_first_what3words_word(service, location, expected):
    assert service._extract_location_part(location) == expected


# --- full identifier -------------------------------------------------------


def test_generate_combines_location_keyword_and_sequence(app, service):
    assert service.generate("filled.count.soap", "<p>roof leaking</p>", None) == ("FILLED-ROOF-001")


def test_generate_skips_identifiers_already_taken(app, service):
    db.session.add(Case(identifier="FILLED-ROOF-001", user_id=1))
    db.session.commit()
    assert service.generate("filled.count.soap", "roof leaking", None) == "FILLED-ROOF-002"
