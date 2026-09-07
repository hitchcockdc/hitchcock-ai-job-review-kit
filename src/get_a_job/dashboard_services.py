"""Small application services used by the local dashboard HTTP adapter."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from get_a_job.matching import score_job
from get_a_job.models import CandidateProfile, Job
from get_a_job.ranking import shortlist
from get_a_job.resume import save_tailored_resume_draft, tailored_resume_draft
from get_a_job.storage import Store


class ApplicationService:
    def __init__(self, store: Store) -> None:
        self.store = store

    def applications(self) -> list[dict[str, object]]:
        return self.store.list_applications()

    def save_followup(self, job_key: str, follow_up_date: str, reminder_note: str) -> None:
        self.store.save_application_followup(job_key, follow_up_date, reminder_note)


class ScoringPreviewService:
    """Compare tentative weights against the local new-role queue without saving them."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def preview(self, weights: object, limit: int = 10) -> dict[str, object]:
        current_profile = self.store.load_profile()
        proposed_profile = CandidateProfile.from_dict(
            {**asdict(current_profile), "scoring_weights": weights}
        )
        ignored = set(
            current_profile.preferences_to_confirm.get("ignored_learning_terms", [])
        )
        signals = self.store.decision_signals().filtered(ignored)
        jobs = self.store.list_jobs(["new"])
        ranking_limit = max(limit * 3, 30)
        current = shortlist(
            current_profile,
            jobs,
            limit=ranking_limit,
            per_company=1,
            decision_signals=signals,
        )
        proposed = shortlist(
            proposed_profile,
            jobs,
            limit=ranking_limit,
            per_company=1,
            decision_signals=signals,
        )

        current_by_key = {
            job.key: (rank, result.score, job)
            for rank, (result, job) in enumerate(current, start=1)
        }
        proposed_by_key = {
            job.key: (rank, result.score, job)
            for rank, (result, job) in enumerate(proposed, start=1)
        }
        visible_keys = {job.key for _, job in current[:limit]} | {
            job.key for _, job in proposed[:limit]
        }
        ordered_keys = sorted(
            visible_keys,
            key=lambda key: (
                proposed_by_key.get(key, (ranking_limit + 1, 0, None))[0],
                current_by_key.get(key, (ranking_limit + 1, 0, None))[0],
            ),
        )
        rows: list[dict[str, object]] = []
        for key in ordered_keys:
            current_value = current_by_key.get(key)
            proposed_value = proposed_by_key.get(key)
            selected_value = proposed_value or current_value
            if selected_value is None:
                continue
            job = selected_value[2]
            rows.append(
                {
                    "job_key": key,
                    "title": job.title,
                    "company": job.company,
                    "current_score": current_value[1] if current_value else None,
                    "proposed_score": proposed_value[1] if proposed_value else None,
                    "current_rank": current_value[0] if current_value else None,
                    "proposed_rank": proposed_value[0] if proposed_value else None,
                }
            )
        return {
            "rows": rows,
            "current_weights": current_profile.scoring_weights,
            "proposed_weights": proposed_profile.scoring_weights,
            "queue_size": len(jobs),
            "persisted": False,
        }


class TailoringService:
    def __init__(self, store: Store, config_dir: Path) -> None:
        self.store = store
        self.config_dir = config_dir

    @staticmethod
    def file_hash(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    def create_draft(self, job_key: str) -> tuple[dict[str, object], Job, Path]:
        resume_path = self.config_dir / "resume.private.txt"
        if not resume_path.exists():
            raise ValueError("upload a readable resume before creating a tailored draft")
        profile: CandidateProfile = self.store.load_profile()
        job = self.store.get_job(job_key)
        match = score_job(profile, job)
        draft = tailored_resume_draft(
            resume_path.read_text(encoding="utf-8"), job_title=job.title, company=job.company,
            matched_skills=match.matched_skills, matched_required_skills=match.matched_required_skills,
            missing_skills=match.missing_skills, evidence=match.evidence,
        )
        return draft, job, resume_path

    def approve(self, draft: dict[str, object], job: Job, resume_path: Path) -> dict[str, object]:
        docx = self.config_dir / "resume.private.docx"
        approved = {**draft, "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "job_key": job.key,
                    "resume_text_hash": self.file_hash(resume_path), "docx_hash": self.file_hash(docx) if docx.exists() else ""}
        plan_id = sha256(f"{job.key}|{approved['approved_at']}|{approved['resume_text_hash']}".encode()).hexdigest()[:32]
        approved["plan_id"] = plan_id
        path = self.config_dir / "tailoring-plans" / f"{plan_id}.private.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        save_tailored_resume_draft(path, approved)
        return approved

    @staticmethod
    def select_experience_evidence(draft: dict[str, object], selected_evidence: object) -> dict[str, object]:
        if not isinstance(selected_evidence, list) or not all(isinstance(item, str) for item in selected_evidence):
            raise ValueError("selected experience evidence must be a list of text items")
        options = {str(item) for item in draft.get("experience_bullet_options", [])}
        requested = [item.strip() for item in selected_evidence if item.strip()]
        if any(item not in options for item in requested):
            raise ValueError("selected experience evidence must come from this resume draft")
        return {**draft, "selected_experience_bullets": list(dict.fromkeys(requested))}

    def approved_plan(self, plan_id: str, job_key: str) -> tuple[dict[str, object], Job]:
        if len(plan_id) != 32 or any(char not in "0123456789abcdef" for char in plan_id):
            raise ValueError("an approved tailoring plan is required before generating")
        try:
            plan = json.loads((self.config_dir / "tailoring-plans" / f"{plan_id}.private.json").read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError("the approved tailoring plan was not found") from error
        job = self.store.get_job(job_key)
        if plan.get("job_key") != job.key:
            raise ValueError("the approved tailoring plan belongs to a different role")
        resume = self.config_dir / "resume.private.txt"; docx = self.config_dir / "resume.private.docx"
        if not resume.exists() or not docx.exists() or plan.get("docx_hash") != self.file_hash(docx) or plan.get("resume_text_hash") != self.file_hash(resume):
            raise ValueError("the resume changed after approval; create and approve a new plan")
        return plan, job
