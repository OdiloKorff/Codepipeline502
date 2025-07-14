"""Grafana / InfluxDB time‑series writer for RL‑metrics.

Designed to be dependency‑light: if `influxdb_client` is missing, we fall back to
a simple line‑protocol HTTP request.  In dry‑run mode (default when no creds
present) we just `print` the payload so unit‑tests can validate the flow
without network or external service.
"""

from __future__ import annotations

import os
import json
import time
import logging
from typing import Any, Dict

_log = get_logger(__name__)

INFLUX_URL = os.getenv("INFLUX_URL")           # e.g. http://localhost:8086
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "codepipeline")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "rl_metrics")
DRY_RUN = INFLUX_URL is None or INFLUX_URL.strip() == ""

def _line_protocol(metric: str, fields: Dict[str, Any], tags: Dict[str, str] | None = None) -> str:
    tag_str = ",".join(f"{k}={v}" for k, v in (tags or {}).items())
    field_str = ",".join(f"{k}={json.dumps(v) if isinstance(v, str) else v}" for k, v in fields.items())
    ts = int(time.time() * 1_000_000_000)  # nanoseconds timestamp
    return f"{metric}{',' if tag_str else ''}{tag_str} {field_str} {ts}"

def write(metrics: Dict[str, Any], run_id: str | None = None, *, prefix: str = "rl") -> bool:
    """Write *metrics* dict to InfluxDB.

    Returns True on success (or dry‑run), False otherwise.
    """
    line = _line_protocol(
        metric=f"{prefix}_metrics",
        fields=metrics,
        tags={"run_id": run_id or "unknown"},
    )

    if DRY_RUN:
        _log.info("Dry‑run write: %s", line)
        print(line)
        return True

    try:
        from influxdb_client import InfluxDBClient  # type: ignore
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            client.write_api().write(INFLUX_BUCKET, INFLUX_ORG, record=line)
        _log.info("Metrics written via influxdb‑client")
        return True
    except ModuleNotFoundError:
        _log.debug("influxdb_client not installed, falling back to raw HTTP")

    import requests  # late import to avoid heavy dep if unused
    url = f"{INFLUX_URL}/api/v2/write?org={INFLUX_ORG}&bucket={INFLUX_BUCKET}&precision=ns"
    headers = {"Authorization": f"Token {INFLUX_TOKEN}"} if INFLUX_TOKEN else {}
    resp = requests.post(url, data=line.encode(), headers=headers, timeout=5)
    if resp.status_code >= 300:
        _log.error("Failed to write metrics: %s", resp.text[:200])
        return False
    _log.info("Metrics written via HTTP")
    return True