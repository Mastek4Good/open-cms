import subprocess

import pytest

from hooks import checks

# Built from pieces so this file does not itself trip the private-key and
# merge-conflict checks.
KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
CONFLICT_START = "<" * 7 + " HEAD"
CONFLICT_END = ">" * 7 + " branch"


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return str(path)


def test_trailing_whitespace_is_stripped_and_reported(tmp_path):
    path = write(tmp_path, "a.txt", "one  \ntwo\t\nthree\n")
    assert checks.trailing_whitespace([path])
    assert (tmp_path / "a.txt").read_text() == "one\ntwo\nthree\n"
    assert not checks.trailing_whitespace([path])


def test_trailing_whitespace_preserves_crlf(tmp_path):
    path = write(tmp_path, "a.txt", b"one  \r\ntwo\r\n")
    checks.trailing_whitespace([path])
    assert (tmp_path / "a.txt").read_bytes() == b"one\r\ntwo\r\n"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (b"text", b"text\n"),
        (b"text\n\n\n", b"text\n"),
        (b"text\r\n\r\n", b"text\r\n"),
        (b"\n\n", b""),
    ],
)
def test_end_of_file_fixer(tmp_path, before, after):
    path = write(tmp_path, "a.txt", before)
    assert checks.end_of_file([path])
    assert (tmp_path / "a.txt").read_bytes() == after


def test_end_of_file_leaves_good_empty_and_binary_files_alone(tmp_path):
    good = write(tmp_path, "good.txt", "ok\n")
    empty = write(tmp_path, "empty.txt", b"")
    binary = write(tmp_path, "b.bin", b"\0\x01\x02\n\n")
    assert checks.end_of_file([good, empty, binary]) == []
    assert (tmp_path / "b.bin").read_bytes() == b"\0\x01\x02\n\n"


def test_check_yaml(tmp_path):
    good = write(tmp_path, "good.yml", "a: 1\n---\nb: 2\n")
    bad = write(tmp_path, "bad.yml", "a: [unclosed\n")
    assert checks.check_yaml([good]) == []
    assert len(checks.check_yaml([bad])) == 1


def test_check_toml(tmp_path):
    good = write(tmp_path, "good.toml", 'a = "b"\n')
    bad = write(tmp_path, "bad.toml", "a = \n")
    assert checks.check_toml([good]) == []
    assert len(checks.check_toml([bad])) == 1


def test_merge_conflict_markers(tmp_path):
    clean = write(tmp_path, "clean.txt", "heading\n=======\n")
    conflicted = write(tmp_path, "c.txt", f"a\n{CONFLICT_START}\nb\n{CONFLICT_END}\n")
    assert checks.check_merge_conflict([clean]) == []
    assert len(checks.check_merge_conflict([conflicted])) == 2


def test_large_files(tmp_path):
    small = write(tmp_path, "small.txt", "x" * 1024)
    big = write(tmp_path, "big.txt", "x" * (checks.MAX_FILE_KB * 1024 + 1))
    assert checks.check_large_files([small]) == []
    assert len(checks.check_large_files([big])) == 1


def test_private_keys(tmp_path):
    clean = write(tmp_path, "clean.txt", "nothing secret\n")
    leaked = write(tmp_path, "id_rsa", f"{KEY_HEADER}\nabc\n")
    assert checks.check_private_keys([clean]) == []
    assert len(checks.check_private_keys([leaked])) == 1


def test_check_branch(monkeypatch):
    def fake_run(branch):
        return lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=f"{branch}\n")

    monkeypatch.setattr(checks.subprocess, "run", fake_run("main"))
    assert checks.check_branch([]) != []
    assert checks.check_branch(["main", "release"]) != []

    monkeypatch.setattr(checks.subprocess, "run", fake_run("feat/thing"))
    assert checks.check_branch([]) == []

    monkeypatch.setattr(checks.subprocess, "run", fake_run("release"))
    assert checks.check_branch(["release"]) != []


@pytest.mark.parametrize(
    "message",
    [
        "feat: add thing",
        "fix(auth): handle empty code",
        "chore!: drop old api",
        "docs: explain\n\nlong body here",
        "Merge pull request #3 from x/y",
        'Revert "feat: add thing"',
        "fixup! feat: add thing",
        "# comment first\nfeat: after comment",
    ],
)
def test_conventional_messages_accepted(tmp_path, message):
    assert checks.check_commit_message([write(tmp_path, "MSG", message)]) == []


@pytest.mark.parametrize(
    "message", ["Updated the readme", "feat:no space", "feat: ", "", "Feat: x"]
)
def test_non_conventional_messages_rejected(tmp_path, message):
    assert checks.check_commit_message([write(tmp_path, "MSG", message)]) != []


def test_main_exit_codes(tmp_path, capsys):
    good = write(tmp_path, "good.toml", "a = 1\n")
    bad = write(tmp_path, "bad.toml", "a = \n")
    assert checks.main(["check-toml", good]) == 0
    assert checks.main(["check-toml", bad]) == 1
    assert "invalid TOML" in capsys.readouterr().out
    assert checks.main(["nonsense"]) == 2
    assert checks.main([]) == 2
