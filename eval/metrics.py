def labels(pairs) -> list[str]:
    return sorted({label for pair in pairs for label in pair})


def confusion(pairs) -> dict[tuple[str, str], int]:
    matrix: dict[tuple[str, str], int] = {}
    for expected, predicted in pairs:
        matrix[(expected, predicted)] = matrix.get((expected, predicted), 0) + 1
    return matrix


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def per_class(pairs) -> dict[str, dict[str, float]]:
    matrix = confusion(pairs)
    report = {}
    for label in labels(pairs):
        true_positives = matrix.get((label, label), 0)
        predicted = sum(count for (_, guess), count in matrix.items() if guess == label)
        actual = sum(count for (truth, _), count in matrix.items() if truth == label)
        precision = _ratio(true_positives, predicted)
        recall = _ratio(true_positives, actual)
        report[label] = {
            "support": actual,
            "true_positives": true_positives,
            "false_positives": predicted - true_positives,
            "false_negatives": actual - true_positives,
            "precision": precision,
            "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall) if precision + recall else 0.0,
        }
    return report


def macro(report: dict[str, dict[str, float]]) -> dict[str, float]:
    if not report:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        metric: round(sum(row[metric] for row in report.values()) / len(report), 4)
        for metric in ("precision", "recall", "f1")
    }


def accuracy(pairs) -> float:
    pairs = list(pairs)
    return _ratio(sum(1 for expected, predicted in pairs if expected == predicted), len(pairs))


def iou(first, second) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    overlap_width = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    overlap_height = max(0, min(ay + ah, by + bh) - max(ay, by))
    intersection = overlap_width * overlap_height
    return _ratio(intersection, aw * ah + bw * bh - intersection)
