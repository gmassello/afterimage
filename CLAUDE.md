# afterimage

Visual inspection agent with longitudinal memory, built for the OpenCV AI Competition 2026.

Full brief, rules, architecture and weekly plan: see `docs/BRIEF.md`.

## Hard rules for every coding session

- OpenCV 5 only. Verify every OpenCV API against https://docs.opencv.org/5.x/ before using it — model training data covers OpenCV 4, and OpenCV 5 broke compatibility (`Features2D` replaced by `Features`, C API removed, ML/G-API moved to contrib).
- Design for CPU/Graviton (arm64). The OpenCV 5 DNN engine has no GPU support.
- The agentic loop lives in the product, not in the development process. Every agent decision must be reconstructible from a trace, with the numeric value that triggered it.
- Pin dependencies to exact versions in `requirements.txt`.
- All repo output in English: code, docs, commits, CI.
