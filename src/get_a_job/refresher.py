from __future__ import annotations

import json
import threading
from pathlib import Path

from get_a_job.connectors import fetch_sources_resilient
from get_a_job.storage import Store


def _load_sources(source_path: Path) -> list[dict[str, object]]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("source configuration must contain a JSON list")
    if source_path.name == "sources.json":
        private_path = source_path.with_name("sources.private.json")
        if private_path.exists():
            private_payload = json.loads(private_path.read_text(encoding="utf-8"))
            if not isinstance(private_payload, list):
                raise ValueError("private source configuration must contain a JSON list")
            payload.extend(private_payload)
    return payload


def refresh_sources(store: Store, source_path: Path, stale_after_days: int = 30) -> dict[str, int]:
    payload = _load_sources(source_path)
    results = fetch_sources_resilient(payload)
    for result in results:
        store.record_source_fetch(result)
    report = store.upsert_jobs([job for result in results for job in result.jobs])
    fetched = sum(len(result.jobs) for result in results)
    successful_sources = [result.source_id for result in results if result.error is None]
    expired = store.expire_stale_jobs_for_sources(successful_sources, stale_after_days)
    return {"fetched": fetched, "new": report.inserted, "changed": report.changed, "expired": expired}


class SourceRefresher:
    def __init__(self, store: Store, source_path: Path, interval_minutes: int):
        self.store = store
        self.source_path = source_path
        self.interval_seconds = interval_minutes * 60
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="source-refresher")

    def start(self) -> None:
        if self.source_path.exists() and self.interval_seconds > 0:
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            try:
                refresh_sources(self.store, self.source_path)
            except Exception:
                # Individual failures are recorded by the connector pipeline; the next interval retries.
                continue
