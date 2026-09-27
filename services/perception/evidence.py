from functools import lru_cache

import cv2
import numpy as np

BOX_COLOUR = (60, 76, 231)
TEXT_COLOUR = (255, 255, 255)
TEXT_PX = 18
PAD = 6


@lru_cache(maxsize=1)
def _font():
    return cv2.FontFace("sans")


def annotate(image: np.ndarray, bbox: tuple[int, int, int, int], text: str) -> np.ndarray:
    canvas = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    x, y, width, height = bbox
    cv2.rectangle(canvas, (x, y), (x + width, y + height), BOX_COLOUR, 2)
    box = cv2.getTextSize(canvas.shape[1::-1], text, (0, 0), _font(), TEXT_PX)
    label_height = box[3] + 2 * PAD
    top = y - label_height if y >= label_height else y + height
    cv2.rectangle(canvas, (x, top), (x + box[2] + 2 * PAD, top + label_height), BOX_COLOUR, -1)
    cv2.putText(
        canvas, text, (x + PAD, top + PAD), TEXT_COLOUR, _font(), TEXT_PX,
        flags=cv2.PUT_TEXT_ORIGIN_TL,
    )
    return canvas
