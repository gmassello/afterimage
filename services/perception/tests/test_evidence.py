import numpy as np

from services.perception import evidence

BOX = (100, 120, 80, 60)


def test_the_region_is_boxed_and_labelled_without_touching_the_input(panel):
    before = panel.copy()
    drawn = evidence.annotate(panel, BOX, "crack · score 0.69 · Δ-42")

    assert np.array_equal(panel, before)
    x, y, width, height = BOX
    assert tuple(drawn[y, x + width // 2]) == evidence.BOX_COLOUR
    assert (drawn[:y, x:x + width] != panel[:y, x:x + width]).any()


def test_unicode_text_is_drawn_as_its_own_glyphs(panel):
    accented = evidence.annotate(panel, BOX, "Inspección ✓ Δ")
    ascii_only = evidence.annotate(panel, BOX, "Inspeccion ? D")

    assert (accented != ascii_only).any()


def test_a_region_at_the_top_edge_puts_its_label_below(panel):
    drawn = evidence.annotate(panel, (10, 0, 50, 40), "hotspot")

    assert (drawn[41:70, 10:60] != panel[41:70, 10:60]).any()


def test_a_grayscale_image_is_annotated_in_colour(panel):
    gray = panel[:, :, 0]

    assert evidence.annotate(gray, BOX, "soiling").shape == (*gray.shape, 3)
