export type Status = 'new' | 'saved' | 'rejected' | 'applied';
export type ScoringWeightKey =
  | 'required_skills'
  | 'role_skills'
  | 'title_target'
  | 'priority'
  | 'work_location'
  | 'preferences'
  | 'industry';
export type ScoringWeights = Record<ScoringWeightKey, number>;
export type LocationVerificationFilter = 'all' | 'verified' | 'unknown';
export type AuthorizationVerificationFilter =
  | 'all'
  | 'verified'
  | 'sponsorship_required'
  | 'unknown';

export type Job = {
  key: string;
  title: string;
  company: string;
  url: string;
  description: string;
  location: string;
  remote: boolean;
  country: string;
  countries?: string[];
  regions?: string[];
  employment_type: string;
  salary_min: number | null;
  salary_max: number | null;
};

export type SkillContext = {
  skill: string;
  confidence: 'high' | 'medium' | 'low';
  context: string;
};

export type Match = {
  score: number;
  reasons: string[];
  evidence: string[];
  matched_skills: string[];
  missing_skills: string[];
  matched_required_skills: string[];
  matched_preferred_skills: string[];
  required_role_skills: string[];
  buried_role_skills: string[];
  country_verification: string;
  authorization_verification: string;
  matched_role_skill_count?: number;
  role_skill_count?: number;
  role_skill_contexts?: SkillContext[];
  score_breakdown: Record<string, number>;
  scoring_weights?: ScoringWeights;
};

export type Item = { job: Job; match: Match; status: Status };
export type Source = {
  source_id: string;
  fetched_at: string;
  job_count: number;
  error: string | null;
};
export type Decision = {
  job_key: string;
  status: Status;
  note: string;
  decided_at: string;
  title?: string;
  company?: string;
  url?: string;
};

export type Profile = Record<string, unknown> & {
  skills: string[];
  skill_aliases: Record<string, string[]>;
  remote_ok: boolean;
  minimum_salary: number | null;
  max_travel_percentage: number | null;
  locations: string[];
  employment_types: string[];
  title_priorities: string[];
  eligible_countries: string[];
  work_authorized_countries: string[];
  consider_sponsorship_roles: boolean;
  scoring_weights?: ScoringWeights;
  excluded_terms: string[];
};

export type Config = {
  profile: Profile;
  resume: {
    present: boolean;
    name: string | null;
    source_format: 'docx' | 'pdf' | null;
    docx_present: boolean;
    pdf_present: boolean;
  };
  resume_draft: Profile | null;
  resume_text_preview: string;
};

export type Stats = {
  counts: Record<string, number>;
  activity: { last_fetch_at: string | null };
  sources: Source[];
  learning?: {
    positive_decision_terms: number;
    negative_decision_terms: number;
  };
  candidate_cache?: CandidateCacheStats;
};

export type Learning = {
  terms: {
    positive: { term: string; count: number }[];
    negative: { term: string; count: number }[];
  };
  ignored: string[];
};

export type CandidateCacheStats = {
  hits: number;
  misses: number;
  hit_rate: number;
  entries: number;
  cached_jobs: number;
  estimated_bytes: number;
};

export type QueueMeta = {
  ranking_ms: number;
  cached: boolean;
  candidate_cache?: CandidateCacheStats;
};

export type ScoringPreviewRow = {
  job_key: string;
  title: string;
  company: string;
  current_score: number | null;
  proposed_score: number | null;
  current_rank: number | null;
  proposed_rank: number | null;
};

export type ScoringPreview = {
  rows: ScoringPreviewRow[];
  current_weights: ScoringWeights;
  proposed_weights: ScoringWeights;
  queue_size: number;
  persisted: false;
  current_snapshot_reused: boolean;
  candidate_set_reused: boolean;
};

export type TailoredDraft = {
  target: { title: string; company: string };
  reviewer_instruction: string;
  current_summary: string;
  tailored_summary: string;
  summary_reordered: boolean;
  emphasize_existing_skills: string[];
  reordered_core_expertise: string[];
  supporting_resume_evidence: string[];
  experience_bullet_options: string[];
  selected_experience_bullets: string[];
  experience_bullets_applied?: string[];
  plan_id?: string;
  skills_not_added: string[];
  source_resume_preserved: boolean;
};
