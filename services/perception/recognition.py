from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np

from services.perception import alignment

NEIGHBOURS = 8
TREES = 10


@dataclass(frozen=True)
class IdentityResult:
    asset_id: str | None
    votes: int
    vote_share: float
    runner_up: str | None
    runner_up_votes: int
    query_keypoints: int
    candidates: int


def describe(image: np.ndarray, detector: str) -> np.ndarray | None:
    if detector != alignment.NEURAL:
        return cv2.ORB.create(4000).detectAndCompute(image, None)[1]
    with alignment.NEURAL_LOCK:
        return alignment._aliked().detectAndCompute(image, None)[1]


def _vectors(descriptors: np.ndarray) -> np.ndarray:
    if descriptors.dtype == np.uint8:
        return np.unpackbits(descriptors, axis=1).astype(np.float32)
    return descriptors.astype(np.float32)


# ponytail: binary ORB descriptors are unpacked to bits and searched with the Euclidean metric,
# whose square is the Hamming distance, because ANNINDEX_DIST_HAMMING never finishes build() on
# the many identical descriptors a repetitive cell grid produces
def _index(vectors: np.ndarray):
    index = cv2.ANNIndex.create(vectors.shape[1], cv2.ANNINDEX_DIST_EUCLIDEAN)
    index.setSeed(0)
    index.addItems(vectors)
    index.build(TREES)
    return index


def identify(
    query: np.ndarray | None,
    candidates: dict[str, np.ndarray | None],
    match_ratio: float,
) -> IdentityResult:
    described: dict[str, np.ndarray] = {
        asset_id: d for asset_id, d in candidates.items() if d is not None and len(d)
    }
    if query is None or not len(query) or not described:
        return IdentityResult(None, 0, 0.0, None, 0, 0 if query is None else len(query), len(described))

    owners = np.concatenate([[asset_id] * len(d) for asset_id, d in described.items()])
    index = _index(_vectors(np.concatenate(list(described.values()))))
    neighbours, distances = index.knnSearch(
        np.ascontiguousarray(_vectors(query)), min(NEIGHBOURS, len(owners))
    )
    votes: Counter[str] = Counter()
    for row, dists in zip(neighbours, distances.astype(np.float64)):
        nearest = owners[row[0]]
        rival = next((d for i, d in zip(row[1:], dists[1:]) if owners[i] != nearest), None)
        if rival is None or dists[0] < match_ratio * rival:
            votes[str(nearest)] += 1

    ranked = votes.most_common(2)
    if not ranked:
        return IdentityResult(None, 0, 0.0, None, 0, len(query), len(described))
    winner, winner_votes = ranked[0]
    runner_up, runner_up_votes = ranked[1] if len(ranked) > 1 else (None, 0)
    return IdentityResult(
        asset_id=winner,
        votes=winner_votes,
        vote_share=winner_votes / sum(votes.values()),
        runner_up=runner_up,
        runner_up_votes=runner_up_votes,
        query_keypoints=len(query),
        candidates=len(described),
    )
