import json
import re
from pathlib import Path

import pytest

PAGE = Path("docs/EVALUATION.md")
RESULTS = Path("eval/results/latest/results.json")

pytestmark = pytest.mark.skipif(
    not (PAGE.exists() and RESULTS.exists()), reason="run `make eval` first"
)


@pytest.fixture(scope="module")
def published():
    return PAGE.read_text()


@pytest.fixture(scope="module")
def measured():
    return json.loads(RESULTS.read_text())["summary"]


def _claim(text, pattern):
    match = re.search(pattern, text)
    assert match, f"the page no longer states: {pattern}"
    return match.group(1)


def test_headline_figures_match_the_artefact(published, measured):
    assert _claim(published, r"Branch accuracy \*\*([\d.]+)\*\*") == str(measured["branch"]["accuracy"])
    assert _claim(published, r"Branch accuracy.*?macro F1 \*\*([\d.]+)\*\*") == str(measured["branch"]["macro"]["f1"])
    assert _claim(published, r"Defect accuracy \*\*([\d.]+)\*\*") == str(measured["defect"]["accuracy"])
    assert _claim(published, r"Defect accuracy.*?macro F1 \*\*([\d.]+)\*\*") == str(measured["defect"]["macro"]["f1"])
    assert _claim(published, r"Mean IoU \*\*([\d.]+)\*\*") == str(measured["localisation"]["mean_iou"])


def test_scenario_counts_match_the_artefact(published, measured):
    assert _claim(published, r"\*\*(\d+) passed\*\*") == str(measured["passed"])
    assert _claim(published, r"(\d+) scenarios — \d+ synthetic") == str(measured["scenarios"])
    assert _claim(published, r"scenarios — (\d+) synthetic") == str(measured["synthetic"])
    assert _claim(published, r"synthetic, (\d+) on real") == str(measured["real"])


@pytest.mark.parametrize("heading,key", [("Agent branch", "branch"), ("Defect class", "defect")])
def test_every_published_table_row_matches_the_artefact(published, measured, heading, key):
    section = published.split(f"### {heading}")[1].split("###")[0]
    rows = re.findall(r"\| `(\w+)` \| (\d+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", section)
    report = measured[key]["per_class"]
    assert {label for label, *_ in rows} == set(report), f"{heading}: classes differ"
    for label, support, precision, recall, f1 in rows:
        assert [support, precision, recall, f1] == [
            str(report[label][name]) for name in ("support", "precision", "recall", "f1")
        ], f"{heading}: row `{label}` does not match the artefact"
