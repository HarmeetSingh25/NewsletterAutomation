#!/usr/bin/env python3
"""Generate and download an infographic using Nano Banana via Kie.ai."""

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.kie.ai/api/v1/jobs"


def read_api_key():
    if os.getenv("KIE_API_KEY"):
        return os.environ["KIE_API_KEY"]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "KIE_API_KEY":
                return value.strip().strip("\"'")
    return ""


def request_json(url, api_key, payload=None, timeout=60):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": f"Bearer {api_key}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Kie.ai returned HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Kie.ai: {error.reason}") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Detailed image prompt")
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/infographic.png")
    parser.add_argument("--model", default=os.getenv("KIE_IMAGE_MODEL", "google/nano-banana"))
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    api_key = read_api_key()
    if not api_key:
        parser.error("KIE_API_KEY is missing; add it to .env")
    created = request_json(
        f"{BASE}/createTask", api_key,
        {"model": args.model, "input": {"prompt": args.prompt, "output_format": "png", "aspect_ratio": "16:9"}},
    )
    task_data = created.get("data")
    if not isinstance(task_data, dict):
        raise RuntimeError(f"Kie.ai task creation failed (code {created.get('code')}): {created.get('msg', 'no error message returned')}")
    task_id = task_data.get("taskId")
    if not task_id:
        raise RuntimeError(f"Kie.ai did not return a taskId: {created}")
    deadline, delay = time.monotonic() + args.timeout, 3
    while time.monotonic() < deadline:
        task = request_json(f"{BASE}/recordInfo?taskId={task_id}", api_key).get("data", {})
        state = task.get("state")
        if state == "success":
            result = json.loads(task.get("resultJson") or "{}")
            urls = result.get("resultUrls") or []
            if not urls:
                raise RuntimeError(f"Kie.ai task succeeded without result URLs: {task}")
            with urlopen(urls[0], timeout=120) as response:
                image_data = response.read()
            output = args.output.with_suffix(Path(urlparse(urls[0]).path).suffix or ".png")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(image_data)
            print(f"Downloaded infographic to {output}")
            return
        if state == "fail":
            raise RuntimeError(f"Kie.ai task failed: {task.get('failCode')} {task.get('failMsg')}")
        time.sleep(delay)
        delay = min(delay + 2, 15)
    raise TimeoutError(f"Timed out waiting for Kie.ai task {task_id}")


if __name__ == "__main__":
    main()
