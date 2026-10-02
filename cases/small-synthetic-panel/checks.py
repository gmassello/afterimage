import json
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib

TIMEOUT = 120
RESET = None
JSON = {"Accept": "application/json"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def png(width, height, pixel):
    rows = b"".join(
        b"\x00" + bytes(pixel(x, y) for x in range(width)) for y in range(height)
    )

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


SHARP = png(256, 256, lambda x, y: 60 if (x // 16 + y // 16) % 2 else 190)
FLAT = png(256, 256, lambda x, y: 128)


def call(base, method, path, body=None, headers=None, raw=None):
    headers = dict(headers or {})
    data = raw
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            status, payload, location = resp.status, resp.read(), resp.headers.get("Location")
    except urllib.error.HTTPError as err:
        status, payload, location = err.code, err.read(), err.headers.get("Location")
    try:
        parsed = json.loads(payload) if payload else None
    except ValueError:
        parsed = payload.decode("utf-8", "replace")
    return status, parsed, location


def upload(base, asset_id, image):
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="asset_id"\r\n\r\n{asset_id}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="capture.png"\r\n'
        "Content-Type: image/png\r\n\r\n".encode() + image + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    headers = {**JSON, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    return call(base, "POST", "/inspections", headers=headers, raw=b"".join(parts))


def inspect(base, asset_id, image):
    status, body, location = upload(base, asset_id, image)
    expect(status == 303 and location, f"upload got {status} {body}")
    run_id = location.rstrip("/").split("/")[-1].split("?")[0]
    expect(location.split("?")[0].endswith(f"/traces/{run_id}"), f"redirect to {location}")
    status, body, _ = call(base, "POST", f"/runs/{run_id}/execute", headers=JSON)
    expect(status < 400, f"execute got {status} {body}")
    status, trace, _ = call(base, "GET", f"/traces/{run_id}?format=json", headers=JSON)
    expect(status == 200 and isinstance(trace, (dict, list)), f"trace got {status}")
    return run_id, trace


def decisions(node):
    if isinstance(node, dict):
        if {"input_metric", "value", "threshold", "branch"} <= node.keys():
            yield node
        for value in node.values():
            yield from decisions(value)
    elif isinstance(node, list):
        for value in node:
            yield from decisions(value)


def branches(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "branch" and isinstance(value, str):
                yield value
            yield from branches(value)
    elif isinstance(node, list):
        for value in node:
            yield from branches(value)


def fresh_asset():
    return f"case-small-{uuid.uuid4().hex[:10]}"


def expect(cond, message):
    if not cond:
        raise AssertionError(message)


def expect_error(status, body, want_status, want_code):
    if want_status is not None:
        expect(status == want_status, f"status {status}, want {want_status}")
    expect(isinstance(body, dict), f"body is not JSON: {body!r}"[:200])
    expect(body.get("code") == want_code, f"code {body.get('code')!r}, want {want_code!r}")
    expect(isinstance(body.get("detail"), str) and body["detail"], "detail missing")
    expect(body.get("retryable") is False, f"retryable {body.get('retryable')!r}, want False")


def check_health_reports_aligned_calibration(base):
    status, body, _ = call(base, "GET", "/health", headers=JSON)
    expect(status == 200, f"status {status}")
    expect(body.get("ok") is True, f"ok {body.get('ok')!r}")
    expect((body.get("calibration") or {}).get("branch") == "aligned", f"calibration {body}")


def check_landing_names_the_product(base):
    status, body, _ = call(base, "GET", "/", headers={"Accept": "text/html"})
    expect(status == 200, f"status {status}")
    expect("<title>afterimage" in str(body), "landing title is not afterimage")


def check_invalid_asset_id_is_refused(base):
    status, body, _ = upload(base, "Not A Valid ID!", SHARP)
    expect_error(status, body, 400, "invalid_asset_id")


def check_undecodable_image_is_refused(base):
    status, body, _ = upload(base, fresh_asset(), b"not an image")
    expect_error(status, body, 400, "invalid_image")


def check_first_capture_becomes_the_baseline(base):
    asset = fresh_asset()
    _, trace = inspect(base, asset, SHARP)
    expect("first_baseline" in set(branches(trace)), f"branches {set(branches(trace))}")
    status, _, _ = call(base, "GET", f"/assets/{asset}", headers={"Accept": "text/html"})
    expect(status == 200, f"asset history got {status}")


def check_flat_capture_is_sent_back_with_its_number(base):
    asset = fresh_asset()
    inspect(base, asset, SHARP)
    _, trace = inspect(base, asset, FLAT)
    found = [d for d in decisions(trace) if d["branch"] == "recapture"]
    expect(found, f"no recapture decision; branches {set(branches(trace))}")
    d = found[-1]
    expect(isinstance(d["value"], (int, float)) and isinstance(d["threshold"], (int, float)),
           f"decision without numbers: {d}")
    expect(isinstance(d["input_metric"], str) and d["input_metric"], f"decision without metric: {d}")


def check_unknown_run_cannot_execute(base):
    status, body, _ = call(base, "POST", "/runs/000000000000/execute", headers=JSON)
    expect_error(status, body, 404, "run_not_found")


def check_finished_run_cannot_be_retried(base):
    run_id, _ = inspect(base, fresh_asset(), SHARP)
    status, body, _ = call(base, "POST", f"/runs/{run_id}/retry", headers=JSON)
    expect(400 <= status < 500, f"status {status}")
    expect_error(status, body, None, "run_not_failed")


CHECKS = [
    check_health_reports_aligned_calibration,
    check_landing_names_the_product,
    check_invalid_asset_id_is_refused,
    check_undecodable_image_is_refused,
    check_first_capture_becomes_the_baseline,
    check_flat_capture_is_sent_back_with_its_number,
    check_unknown_run_cannot_execute,
    check_finished_run_cannot_be_retried,
]


def main():
    if len(sys.argv) != 2:
        print("usage: python3 checks.py <base-url>", file=sys.stderr)
        return 2
    base = sys.argv[1].rstrip("/")
    started = time.monotonic()
    results = []
    for check in CHECKS:
        try:
            if RESET:
                call(base, *RESET)
            check(base)
            results.append((check.__name__, None))
        except Exception as exc:
            results.append((check.__name__, f"{type(exc).__name__}: {exc}"))
    failed = [r for r in results if r[1]]
    print(f"checks: {len(results) - len(failed)} passed, {len(failed)} failed, "
          f"{time.monotonic() - started:.1f}s, {base}")
    for name, error in results:
        print(f"{'FAIL' if error else 'ok  '} {name}" + (f" — {error}" if error else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
