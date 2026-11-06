"""Note content handling: visible-text detection (ReDoS-safe) and the length cap."""

import time

import pytest

from app.extensions import db
from app.models.case import Case
from app.models.case_note import CaseNote
from app.models.user import User
from app.services.case_service import MAX_NOTE_LENGTH, NOTE_TOO_LONG_ERROR, CaseService
from app.services.html_service import has_visible_text
from tests.conftest import csrf_token, register

# --- has_visible_text ------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    ["hello", "<p>hello</p>", "<p><strong>hi</strong> there</p>", "<p>unclosed", "a<br>b", "<<<<"],
)
def test_text_is_detected(html):
    assert has_visible_text(html)


@pytest.mark.parametrize(
    "html",
    ["", "   ", "\n\r\n", "<p></p>", "<p><br></p>", "<p> </p><p>\n</p>", "<p>&nbsp;</p>", "&nbsp;"],
)
def test_empty_markup_and_whitespace_are_not_text(html):
    assert not has_visible_text(html)


def test_none_is_not_text():
    assert not has_visible_text(None)


# The old implementation, re.sub(r"<[^>]+>", ...), took ~65 seconds on a
# 500,000 character run of "<" (the framework's default form-size limit). These
# inputs are the shapes that make tag-stripping regexes backtrack.
ADVERSARIAL = [
    "<" * 500_000,
    "<a " * 150_000,
    "<p>" * 150_000,
    "<!--" * 120_000,
    "&" * 500_000,
    "<" + "a" * 500_000,
]


@pytest.mark.parametrize("payload", ADVERSARIAL, ids=lambda p: f"{p[:6]!r}x{len(p)}")
def test_adversarial_input_is_processed_in_linear_time(payload):
    started = time.perf_counter()
    has_visible_text(payload)
    assert time.perf_counter() - started < 2.0


# --- length cap -----------------------------------------------------------


@pytest.fixture()
def worker(client):
    register(client, "worker@example.org")
    return User.query.filter_by(email="worker@example.org").one()


@pytest.fixture()
def case(worker):
    case = Case(identifier="SOTS-0001", user_id=worker.id)
    db.session.add(case)
    db.session.commit()
    return case


def post_note(client, case, content):
    return client.post(
        f"/cases/{case.id}/notes",
        data={"csrf_token": csrf_token(client, f"/cases/{case.id}"), "content": content},
        follow_redirects=True,
    )


def test_note_at_the_limit_is_saved_and_over_it_is_rejected(client, case):
    ok = post_note(client, case, "x" * MAX_NOTE_LENGTH)
    assert "Note added." in ok.get_data(as_text=True)
    assert CaseNote.query.filter_by(case_id=case.id).count() == 1

    too_long = post_note(client, case, "x" * (MAX_NOTE_LENGTH + 1))
    assert NOTE_TOO_LONG_ERROR in too_long.get_data(as_text=True)
    assert CaseNote.query.filter_by(case_id=case.id).count() == 1


def test_overlong_voice_transcript_is_rejected(client, case):
    response = client.post(
        f"/cases/{case.id}/notes",
        data={
            "csrf_token": csrf_token(client, f"/cases/{case.id}"),
            "voice_transcript": "x" * (MAX_NOTE_LENGTH + 1),
        },
        follow_redirects=True,
    )
    assert NOTE_TOO_LONG_ERROR in response.get_data(as_text=True)
    assert CaseNote.query.count() == 0


def test_adversarial_note_is_rejected_quickly_by_the_endpoint(client, case):
    started = time.perf_counter()
    response = post_note(client, case, "<" * 150_000)  # ~450 KB once URL-encoded
    assert time.perf_counter() - started < 2.0
    assert NOTE_TOO_LONG_ERROR in response.get_data(as_text=True)


def test_create_case_rejects_overlong_notes_and_transcripts(worker):
    service = CaseService()
    too_long = "x" * (MAX_NOTE_LENGTH + 1)

    created, error = service.create_case(user_id=worker.id, full_name="A", notes_content=too_long)
    assert (created, error) == (None, NOTE_TOO_LONG_ERROR)

    created, error = service.create_case(
        user_id=worker.id, full_name="A", voice_transcript=too_long
    )
    assert (created, error) == (None, NOTE_TOO_LONG_ERROR)

    created, error = service.create_case(
        user_id=worker.id, full_name="A", notes_content="x" * MAX_NOTE_LENGTH
    )
    assert error is None
    assert created is not None


def test_interaction_and_note_edit_reject_overlong_content(worker, case):
    service = CaseService()
    too_long = "x" * (MAX_NOTE_LENGTH + 1)

    interaction, error = service.add_interaction(
        case_id=case.id, user_id=worker.id, note_content=too_long
    )
    assert (interaction, error) == (None, NOTE_TOO_LONG_ERROR)

    note = service.add_note(case_id=case.id, content="<p>short</p>", user_id=worker.id)
    updated, error = service.update_note_content(note.id, too_long, worker.id)
    assert (updated, error) == (None, NOTE_TOO_LONG_ERROR)


def test_worst_case_note_within_the_cap_is_bounded(client, case):
    # sanitize_html still strips <script>/<style> blocks with a backtracking
    # regex, which is quadratic on repeated unclosed tags. The length cap is
    # what keeps that bounded, so pin the worst case that is allowed through.
    payload = "<script>" * (MAX_NOTE_LENGTH // len("<script>"))
    assert len(payload) <= MAX_NOTE_LENGTH

    started = time.perf_counter()
    post_note(client, case, payload)
    assert time.perf_counter() - started < 3.0
