#!/usr/bin/env python3
"""
Tests for nightly_review script scaffolding.
"""
import sys
import os
import datetime
import pytest

# Ensure scripts directory is on path for imports
scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import nightly_review


def test_fetch_history_not_implemented():
    since = datetime.datetime.utcnow()
    with pytest.raises(NotImplementedError):
        nightly_review.fetch_history(since)


def test_analyze_history_not_implemented():
    history = []
    with pytest.raises(NotImplementedError):
        nightly_review.analyze_history(history)


def test_summary_text_empty():
    results = {"todos": [], "errors": [], "flags": [], "improvements": []}
    summary = nightly_review.summary_text(results)
    assert "- TODOs: 0" in summary
    assert "- Errors: 0" in summary
    assert "- Flags: 0" in summary
    assert "- Improvements: 0" in summary


def test_summary_text_counts():
    results = {"todos": ["t"], "errors": ["e1", "e2"], "flags": ["f"], "improvements": ["i1", "i2", "i3"]}
    summary = nightly_review.summary_text(results)
    assert "- TODOs: 1" in summary
    assert "- Errors: 2" in summary
    assert "- Flags: 1" in summary
    assert "- Improvements: 3" in summary


def test_create_prs_dry_run(capsys):
    results = {"todos": ["t1", "t2"]}
    nightly_review.create_prs(results, dry_run=True)
    captured = capsys.readouterr()
    assert "[dry-run] Would create PR for TODO: t1" in captured.out
    assert "[dry-run] Would create PR for TODO: t2" in captured.out


def test_create_issues_dry_run(capsys):
    results = {"flags": ["f1"], "improvements": ["i1", "i2"]}
    nightly_review.create_issues(results, dry_run=True)
    captured = capsys.readouterr()
    assert "[dry-run] Would create issue/task: f1" in captured.out
    assert "[dry-run] Would create issue/task: i1" in captured.out
    assert "[dry-run] Would create issue/task: i2" in captured.out


def test_post_summary_dry_run(capsys):
    summary = "Test summary"
    nightly_review.post_summary(summary, dry_run=True)
    captured = capsys.readouterr()
    assert "Dry run summary:\nTest summary" in captured.out
