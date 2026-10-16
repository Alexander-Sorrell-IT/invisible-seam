from __future__ import annotations

from pathlib import Path

from invisible_seam.extractors.python_security_extractor import (
    extract_python_security_claims,
)
from invisible_seam.matchers.code_matcher import match_claims


def _claims(tmp_path: Path, source: str):
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    return extract_python_security_claims(tmp_path)


def test_detects_format_percent_and_fstring_sql(tmp_path: Path) -> None:
    claims = _claims(
        tmp_path,
        """
def login(c, username, password):
    return c.execute("SELECT * FROM users WHERE u='{}' AND p='{}'".format(username, password))

def create(c, username):
    c.execute("INSERT INTO users VALUES ('%s')" % username)

def change(c, username, password):
    c.execute(f"UPDATE users SET password='{password}' WHERE username='{username}'")
""",
    )
    assert [c.source_line for c in claims] == [3, 6, 9]
    assert {c.subject for c in claims} == {"login", "create", "change"}
    assert all(c.type == "py-sql-format" for c in claims)


def test_detects_sql_built_in_variable_before_execute(tmp_path: Path) -> None:
    claims = _claims(
        tmp_path,
        """
def find(c, name):
    q = "SELECT * FROM users WHERE name = '" + name + "'"
    return c.execute(q)
""",
    )
    assert len(claims) == 1
    assert claims[0].subject == "find"


def test_parameterized_and_constant_sql_are_clean(tmp_path: Path) -> None:
    claims = _claims(
        tmp_path,
        """
def login(c, username):
    return c.execute("SELECT * FROM users WHERE u = ?", (username,))

def count(c):
    return c.execute("SELECT COUNT(*) " + "FROM users")

def greet(name):
    return "hello {}".format(name)
""",
    )
    assert claims == []


def test_matcher_surfaces_python_sql_claim_as_conflict(tmp_path: Path) -> None:
    claims = _claims(
        tmp_path,
        """
def login(c, username):
    return c.execute(f"SELECT * FROM users WHERE u = '{username}'")
""",
    )
    candidates = match_claims(claims, tmp_path)
    assert len(candidates) == 1
    assert candidates[0].conflict is True
