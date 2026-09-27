from services.perception import recognition
from services.perception.alignment import CLASSIC
from services.perception.panels import foreign_panel, shifted, solar_panel, with_crack

RATIO = 0.8


def described(images, detector):
    return {name: recognition.describe(image, detector) for name, image in images.items()}


def test_a_known_panel_is_voted_to_its_own_asset(panel):
    candidates = described({"panel": panel, "other": foreign_panel()}, CLASSIC)
    query = recognition.describe(shifted(with_crack(panel, 2, 4)), CLASSIC)

    result = recognition.identify(query, candidates, RATIO)

    assert result.asset_id == "panel"
    assert result.vote_share > 0.8
    assert result.votes > result.runner_up_votes
    assert result.candidates == 2


def test_a_single_candidate_takes_every_vote_and_leaves_rejection_to_alignment(panel):
    candidates = described({"panel": panel}, CLASSIC)
    query = recognition.describe(foreign_panel(), CLASSIC)

    result = recognition.identify(query, candidates, RATIO)

    assert result.asset_id == "panel"
    assert result.vote_share == 1.0
    assert result.runner_up is None


def test_nothing_to_compare_against_is_no_identity(panel):
    query = recognition.describe(panel, CLASSIC)

    assert recognition.identify(query, {}, RATIO).asset_id is None
    assert recognition.identify(None, described({"panel": panel}, CLASSIC), RATIO).votes == 0


def test_an_ambiguous_pair_splits_the_votes(panel):
    twin = solar_panel(seed=0)
    candidates = described({"left": panel, "right": twin}, CLASSIC)

    result = recognition.identify(recognition.describe(panel, CLASSIC), candidates, RATIO)

    assert result.vote_share < 0.9
