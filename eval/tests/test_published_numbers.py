import json
import re
from pathlib import Path

import pytest

PAGE = Path("docs/EVALUATION.md")
REPORT = Path("docs/TECHNICAL_REPORT.md")
README = Path("README.md")
RESULTS = Path("eval/results/latest/results.json")
SCRIPT = Path("video/script.tsv")

# Read off the screen during the 5 September browser rehearsal — see video/PRODUCTION.md.
ON_CAMERA = {"3.6589", "2483.1292", "1064.0321", "0.9988", "67.7646", "0.6798"}

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


def test_the_report_restates_the_same_figures(measured):
    report = REPORT.read_text()
    assert _claim(report, r"Branch accuracy \| \*\*([\d.]+)\*\*") == str(measured["branch"]["accuracy"])
    assert _claim(report, r"Branch accuracy.*?macro F1 \*\*([\d.]+)\*\*") == str(measured["branch"]["macro"]["f1"])
    assert _claim(report, r"Defect classification accuracy \| \*\*([\d.]+)\*\*") == str(
        measured["defect"]["accuracy"]
    )
    assert _claim(report, r"Defect classification accuracy.*?macro F1 \*\*([\d.]+)\*\*") == str(
        measured["defect"]["macro"]["f1"]
    )
    assert _claim(report, r"Mean IoU of the located region \| \*\*([\d.]+)\*\*") == str(
        measured["localisation"]["mean_iou"]
    )
    assert _claim(report, r"\*\*(\d+) passed\*\*") == str(measured["passed"])
    assert _claim(report, r"\*\*(\d+) scenarios\*\*") == str(measured["scenarios"])
    assert _claim(report, r"\*\* . (\d+) synthetic") == str(measured["synthetic"])
    assert _claim(report, r"synthetic and (\d+) built on") == str(measured["real"])



def test_the_readme_restates_the_same_figures(measured):
    readme = README.read_text()
    rows = dict(re.findall(r"\| ([\w /]+?) \| ([\d./ ]+?) \|", readme))
    assert rows["Branch accuracy"].strip() == str(measured["branch"]["accuracy"])
    assert rows["Defect macro F1"].strip() == str(measured["defect"]["macro"]["f1"])
    assert rows["Mean IoU"].strip() == str(measured["localisation"]["mean_iou"])
    assert rows["Scenarios passed"].strip() == f"{measured['passed']} / {measured['scenarios']}"
    assert _claim(readme, r"macro F1 ([\d.]+)") == str(measured["branch"]["macro"]["f1"])
    assert _claim(readme, r"(\d+) scenarios —") == str(measured["scenarios"])
    assert _claim(readme, r"— (\d+) synthetic") == str(measured["synthetic"])
    assert _claim(readme, r"synthetic, (\d+) on licensed") == str(measured["real"])
    assert _claim(readme, r"\*\*(\d+) pass\*\*") == str(measured["passed"])


def test_every_readme_path_resolves():
    readme = README.read_text()
    targets = re.findall(r'(?:src|href)="([^"]+)"', readme) + re.findall(r"\]\(([^)]+)\)", readme)
    local = {t for t in targets if not t.startswith(("http://", "https://", "#", "mailto:"))}
    assert local, "the README no longer links to anything in the repository"
    missing = sorted(t for t in local if not Path(t.split("#")[0]).exists())
    assert not missing, f"README points at paths that do not exist: {missing}"

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


def test_the_video_script_only_speaks_measured_figures():
    artefact = RESULTS.read_text()
    spoken = set()
    for row in SCRIPT.read_text().splitlines()[1:]:
        spoken |= set(re.findall(r"\d+\.\d{4}", row.split("\t")[1]))
    assert spoken, "the video script no longer states any measured figure"
    unknown = sorted(n for n in spoken if n not in artefact and n not in ON_CAMERA)
    assert not unknown, f"the video states figures nothing measured: {unknown}"
