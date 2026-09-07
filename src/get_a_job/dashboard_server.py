from __future__ import annotations

import argparse
import base64
import binascii
import json
import subprocess
import threading
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from get_a_job.matching import score_job
from get_a_job.ranking import shortlist
from get_a_job.models import CandidateProfile, Job
from get_a_job.refresher import SourceRefresher
from get_a_job.resume import (
    draft_profile, replace_docx_atomically, replace_resume_atomically,
    generate_tailored_docx, tailored_docx_filename,
)
from get_a_job.storage import Store
from get_a_job.dashboard_services import (
    ApplicationService,
    ScoringPreviewService,
    TailoringService,
)


class DashboardHandler(BaseHTTPRequestHandler):
    store: Store
    config_dir: Path
    refresh_minutes: int
    applications: ApplicationService
    scoring_preview: ScoringPreviewService
    tailoring: TailoringService
    allowed_origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
    }
    ranking_cache: dict[tuple[object, ...], dict[str, object]] = {}
    ranking_cache_lock = threading.Lock()
    candidate_cache: dict[tuple[object, ...], tuple[list[Job], int]] = {}
    candidate_cache_lock = threading.Lock()

    def _cached_eligible_candidates(
        self, status: str, profile: CandidateProfile
    ) -> tuple[list[Job], int, bool]:
        """Reuse deserialized jobs whose hard eligibility inputs have not changed."""
        profile_token = json.dumps(
            asdict(profile), sort_keys=True, separators=(",", ":")
        )
        key = (status, profile_token, self.store.ranking_revision(status))
        with self.candidate_cache_lock:
            cached = self.candidate_cache.get(key)
        if cached is not None:
            jobs, queue_size = cached
            return jobs, queue_size, True

        all_jobs = self.store.list_jobs([status])
        eligible_jobs = [
            job
            for job in all_jobs
            if score_job(
                profile,
                job,
                include_evidence=False,
                include_details=False,
                eligibility_only=True,
            ).eligible
        ]
        with self.candidate_cache_lock:
            if len(self.candidate_cache) >= 4:
                self.candidate_cache.clear()
            self.candidate_cache[key] = (eligible_jobs, len(all_jobs))
        return eligible_jobs, len(all_jobs), False

    def _cached_new_queue_snapshot(
        self, profile: CandidateProfile, minimum_limit: int
    ) -> list[dict[str, object]] | None:
        profile_token = json.dumps(
            asdict(profile), sort_keys=True, separators=(",", ":")
        )
        revision = self.store.ranking_revision("new")
        with self.ranking_cache_lock:
            candidates = [
                (int(key[1]), payload)
                for key, payload in self.ranking_cache.items()
                if key[0] == "new"
                and int(key[1]) >= minimum_limit
                and key[2] == profile_token
                and key[3] == revision
            ]
            if not candidates:
                return None
            _, payload = min(candidates, key=lambda candidate: candidate[0])
            cached_jobs = payload.get("jobs", [])
            if not isinstance(cached_jobs, list):
                return None
            return [
                {
                    "job_key": str(item["job"]["key"]),
                    "title": str(item["job"]["title"]),
                    "company": str(item["job"]["company"]),
                    "score": int(item["match"]["score"]),
                }
                for item in cached_jobs[:minimum_limit]
            ]

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        if origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin")
        if origin and origin not in self.allowed_origins:
            self._json({"error": "origin is not allowed"}, HTTPStatus.FORBIDDEN)
            return
        self._json({})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            self._json({"ok": True})
            return
        if parsed.path == "/api/resume-tailor/download":
            name = query.get("name", [""])[0]
            if not name.startswith("tailored-resume-") or not name.endswith(".private.docx") or "/" in name:
                self._json({"error": "invalid tailored resume name"}, HTTPStatus.BAD_REQUEST)
                return
            path = self.config_dir / name
            if not path.exists():
                self._json({"error": "tailored resume not found"}, HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{name.replace(".private", "")}"')
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/stats":
            self._json(
                {
                    "counts": self.store.status_counts(),
                    "activity": self.store.activity_status(),
                    "sources": self.store.source_health(),
                    "refresh_minutes": self.refresh_minutes,
                    "learning": self.store.decision_signals().summary,
                }
            )
            return
        if parsed.path == "/api/config":
            resume_path = self.config_dir / "resume.private.pdf"
            docx_path = self.config_dir / "resume.private.docx"
            text_path = self.config_dir / "resume.private.txt"
            profile = self.store.load_profile()
            resume_text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
            active_path = docx_path if docx_path.exists() else resume_path
            source_format = "docx" if docx_path.exists() else "pdf" if resume_path.exists() else None
            self._json(
                {
                    "profile": asdict(profile),
                    "resume": {
                        "present": active_path.exists(),
                        "name": active_path.name if active_path.exists() else None,
                        "size": active_path.stat().st_size if active_path.exists() else None,
                        "updated_at": active_path.stat().st_mtime if active_path.exists() else None,
                        "source_format": source_format,
                        "docx_present": docx_path.exists(),
                        "pdf_present": resume_path.exists(),
                    },
                    "resume_draft": draft_profile(profile, resume_text) if resume_text else None,
                    # A resume draft already uses the complete extracted text. Return that
                    # same text for review so the UI cannot imply that the PDF ended at an
                    # arbitrary preview boundary.
                    "resume_text_preview": resume_text,
                }
            )
            return
        if parsed.path == "/api/jobs":
            status = query.get("status", ["new"])[0]
            if status not in {"new", "saved", "rejected", "applied"}:
                self._json({"error": "invalid status"}, HTTPStatus.BAD_REQUEST)
                return
            limit = min(max(int(query.get("limit", ["25"])[0]), 1), 100)
            profile = self.store.load_profile()
            profile_token = json.dumps(asdict(profile), sort_keys=True, separators=(",", ":"))
            cache_key = (status, limit, profile_token, self.store.ranking_revision(status))
            started = time.perf_counter()
            cached = False
            with self.ranking_cache_lock:
                payload = self.ranking_cache.get(cache_key)
                if payload is None:
                    candidate_jobs, _, candidate_cache_reused = (
                        self._cached_eligible_candidates(status, profile)
                    )
                    ignored = set(profile.preferences_to_confirm.get("ignored_learning_terms", []))
                    ranked = shortlist(
                        profile,
                        candidate_jobs,
                        limit=limit,
                        per_company=1,
                        decision_signals=self.store.decision_signals().filtered(ignored),
                        eligibility_prevalidated=True,
                    )
                    payload = {
                        "jobs": [
                            {
                                "job": {"key": job.key, **asdict(job)},
                                "match": asdict(result),
                                "status": status,
                            }
                            for result, job in ranked
                        ],
                        "candidate_cache_reused": candidate_cache_reused,
                    }
                    if len(self.ranking_cache) >= 16:
                        self.ranking_cache.clear()
                    self.ranking_cache[cache_key] = payload
                else:
                    cached = True
            payload = {**payload, "meta": {"ranking_ms": round((time.perf_counter() - started) * 1000), "cached": cached}}
            self._json(payload)
            return
        if parsed.path == "/api/decisions":
            self._json({"decisions": self.store.list_decision_history(50)})
            return
        if parsed.path == "/api/application-followups":
            self._json({"followups": self.store.list_application_followups()})
            return
        if parsed.path == "/api/applications":
            self._json({"applications": self.applications.applications()})
            return
        if parsed.path == "/api/learning":
            profile = self.store.load_profile()
            ignored = set(profile.preferences_to_confirm.get("ignored_learning_terms", []))
            signals = self.store.decision_signals().filtered(ignored)
            self._json({"terms": signals.top_terms(), "ignored": sorted(ignored), "summary": signals.summary})
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/scoring-preview":
            try:
                payload = self._read_json()
                requested_limit = payload.get("limit", 10)
                if not isinstance(requested_limit, int) or isinstance(requested_limit, bool):
                    raise ValueError("limit must be a whole number")
                limit = min(max(requested_limit, 1), 20)
                profile = self.store.load_profile()
                current_snapshot = self._cached_new_queue_snapshot(
                    profile, max(limit * 3, 30)
                )
                eligible_jobs, queue_size, candidate_set_reused = (
                    self._cached_eligible_candidates("new", profile)
                )
                preview = self.scoring_preview.preview(
                    payload.get("weights"),
                    limit,
                    current_snapshot,
                    eligible_jobs,
                    queue_size,
                    candidate_set_reused,
                )
            except (ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._json(preview)
            return
        if parsed.path == "/api/config/profile":
            try:
                payload = self._read_json()
                profile = CandidateProfile.from_dict(payload["profile"])
                self.store.save_profile(profile)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"ok": True, "profile": asdict(profile)})
            return
        if parsed.path == "/api/application-followups":
            try:
                payload = self._read_json()
                job_key = str(payload.get("job_key", "")).strip()
                follow_up_date = str(payload.get("follow_up_date", "")).strip()
                reminder_note = str(payload.get("reminder_note", "")).strip()
                if not job_key:
                    raise ValueError("job_key is required")
                self.applications.save_followup(job_key, follow_up_date, reminder_note)
            except (ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"ok": True})
            return
        if parsed.path == "/api/config/resume":
            try:
                payload = self._read_json(max_bytes=15 * 1024 * 1024)
                encoded = str(payload.get("content_base64", ""))
                data = base64.b64decode(encoded, validate=True)
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError("resume must be smaller than 10 MB")
                filename = str(payload.get("filename", "")).lower()
                self.config_dir.mkdir(parents=True, exist_ok=True)
                if filename.endswith(".docx"):
                    replace_docx_atomically(
                        self.config_dir / "resume.private.docx",
                        self.config_dir / "resume.private.txt",
                        data,
                    )
                elif filename.endswith(".pdf") and data.startswith(b"%PDF-"):
                    if (self.config_dir / "resume.private.docx").exists():
                        raise ValueError("a DOCX is already the preferred resume source; upload a DOCX to replace it")
                    replace_resume_atomically(
                        self.config_dir / "resume.private.pdf",
                        self.config_dir / "resume.private.txt",
                        data,
                    )
                else:
                    raise ValueError("resume must be a DOCX or PDF file")
            except (ValueError, binascii.Error, json.JSONDecodeError, OSError, subprocess.SubprocessError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"ok": True})
            return
        if parsed.path in {"/api/resume-tailor/draft", "/api/resume-tailor/save", "/api/resume-tailor/generate"}:
            try:
                payload = self._read_json()
                job_key = str(payload.get("job_key", "")).strip()
                if not job_key:
                    raise ValueError("job_key is required")
                if parsed.path.endswith("/generate"):
                    draft, job = self.tailoring.approved_plan(str(payload.get("plan_id", "")).strip(), job_key)
                    source = self.config_dir / "resume.private.docx"
                else:
                    draft, job, resume_path = self.tailoring.create_draft(job_key)
                draft = self.tailoring.select_experience_evidence(draft, payload.get("selected_experience_bullets", []))
                if parsed.path.endswith("/save"):
                    draft = self.tailoring.approve(draft, job, resume_path)
                if parsed.path.endswith("/generate"):
                    self.config_dir.mkdir(parents=True, exist_ok=True)
                    filename = tailored_docx_filename(job.company, job.title)
                    draft["experience_bullets_applied"] = generate_tailored_docx(source, self.config_dir / filename, draft)
                    draft["generated_filename"] = filename
            except (ValueError, json.JSONDecodeError, OSError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            filename = draft.get("generated_filename")
            self._json({
                "ok": True, "draft": draft, "saved": parsed.path.endswith("/save"),
                "generated": bool(filename),
                "download_url": f"/api/resume-tailor/download?name={filename}" if filename else None,
            })
            return
        if parsed.path == "/api/learning/ignore":
            try:
                payload = self._read_json()
                term = str(payload.get("term", "")).strip().lower()
                if not term:
                    raise ValueError("term is required")
                profile_data = asdict(self.store.load_profile())
                preferences = dict(profile_data["preferences_to_confirm"])
                ignored = set(preferences.get("ignored_learning_terms", []))
                if bool(payload.get("ignored", True)):
                    ignored.add(term)
                else:
                    ignored.discard(term)
                preferences["ignored_learning_terms"] = sorted(ignored)
                profile_data["preferences_to_confirm"] = preferences
                self.store.save_profile(CandidateProfile.from_dict(profile_data))
            except (ValueError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"ok": True})
            return
        prefix = "/api/jobs/"
        suffix = "/review"
        if not (parsed.path.startswith(prefix) and parsed.path.endswith(suffix)):
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        job_key = unquote(parsed.path[len(prefix) : -len(suffix)].rstrip("/"))
        try:
            payload = self._read_json()
            self.store.set_review(job_key, str(payload.get("status")), str(payload.get("note", "")))
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._json({"ok": True})

    def _read_json(self, max_bytes: int = 1024 * 1024) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > max_bytes:
            raise ValueError("request is too large")
        payload = json.loads(self.rfile.read(length) or "{}")
        if not isinstance(payload, dict):
            raise ValueError("request must be a JSON object")
        return payload

    def log_message(self, format: str, *args: object) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the local get-a-job dashboard API")
    parser.add_argument("--db", default="get_a_job.db")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--refresh-minutes", type=int, default=180)
    args = parser.parse_args(argv)
    DashboardHandler.store = Store(Path(args.db))
    DashboardHandler.applications = ApplicationService(DashboardHandler.store)
    DashboardHandler.scoring_preview = ScoringPreviewService(DashboardHandler.store)
    DashboardHandler.config_dir = Path(args.db).parent / "config"
    DashboardHandler.tailoring = TailoringService(DashboardHandler.store, DashboardHandler.config_dir)
    DashboardHandler.refresh_minutes = max(args.refresh_minutes, 0)
    refresher = SourceRefresher(
        DashboardHandler.store,
        DashboardHandler.config_dir / "sources.json",
        DashboardHandler.refresh_minutes,
    )
    if not (DashboardHandler.config_dir / "sources.json").exists():
        refresher = SourceRefresher(
            DashboardHandler.store,
            Path(args.db).parent / "config" / "sources.private.json",
            DashboardHandler.refresh_minutes,
        )
    refresher.start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard API listening on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        refresher.stop()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
