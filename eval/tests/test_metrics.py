from eval import metrics

PAIRS = [
    ("CRACK", "CRACK"),
    ("CRACK", "CRACK"),
    ("CRACK", "UNKNOWN"),
    ("HOTSPOT", "CRACK"),
    ("HOTSPOT", "HOTSPOT"),
    ("UNKNOWN", "UNKNOWN"),
]


def test_per_class_matches_hand_computed_counts():
    report = metrics.per_class(PAIRS)
    assert report["CRACK"] == {
        "support": 3,
        "true_positives": 2,
        "false_positives": 1,
        "false_negatives": 1,
        "precision": 0.6667,
        "recall": 0.6667,
        "f1": 0.6667,
    }
    assert report["HOTSPOT"]["recall"] == 0.5
    assert report["HOTSPOT"]["precision"] == 1.0


def test_a_label_never_predicted_scores_zero_without_dividing_by_zero():
    report = metrics.per_class([("SOILING", "UNKNOWN")])
    assert report["SOILING"]["precision"] == 0.0
    assert report["SOILING"]["recall"] == 0.0
    assert report["SOILING"]["f1"] == 0.0


def test_macro_averages_over_classes_not_over_samples():
    report = metrics.per_class(PAIRS)
    expected = round(sum(row["f1"] for row in report.values()) / len(report), 4)
    assert metrics.macro(report)["f1"] == expected


def test_accuracy_counts_exact_matches():
    assert metrics.accuracy(PAIRS) == 0.6667


def test_iou_of_identical_boxes_is_one_and_disjoint_is_zero():
    assert metrics.iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert metrics.iou((0, 0, 10, 10), (50, 50, 10, 10)) == 0.0
    assert metrics.iou((0, 0, 10, 10), (5, 0, 10, 10)) == 0.3333
