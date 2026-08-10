-- 003_schema_policy.sql — do do hien dien cua GPR trong van ban chinh sach.
-- Chay sau 001/002. Idempotent (IF NOT EXISTS).
--
-- Nguon: `ingest/fomc.py` (van ban) + `scoring/policy_gpr_scorer.py` (cham diem).
-- ⚠️ Bang nay KHONG chua cu soc chinh sach tien te. Cai do da co ban do sach hon
-- tu gia phai sinh quanh cua so FOMC — xem docstring `ingest/fomc.py`.

-- Van ban goc, luu de doi chieu duoc trich dan ve sau. Khong luu thi
-- `evidence_check` chi kiem duoc mot lan luc cham roi thoi.
CREATE TABLE IF NOT EXISTS policy_documents (
    doc_id        TEXT PRIMARY KEY,          -- fomc_<loai>_<YYYYMMDDTHHMM>
    doc_type      TEXT        NOT NULL,      -- statement | minutes
    source        TEXT        NOT NULL DEFAULT 'fomc',
    title         TEXT,
    url           TEXT        NOT NULL,      -- trang CO NOI DUNG duoc cham
    release_url   TEXT,                      -- trang thong cao (minutes khac url)
    published_at  TIMESTAMPTZ NOT NULL,      -- den PHUT (#5). Voi minutes day la
                                             -- ngay CONG BO, KHONG phai ngay hop.
    n_chars       INTEGER     NOT NULL,
    text          TEXT        NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_policy_documents_published
    ON policy_documents(published_at);

-- Diem. PK phu MOI truc version: doi model/rubric/prompt la mot dot cham KHAC,
-- khong duoc ghi de len dot cu (CLAUDE.md #4) — khac han `ext_series` von co
-- ban "chay" duy nhat.
CREATE TABLE IF NOT EXISTS policy_gpr_scores (
    doc_id            TEXT        NOT NULL REFERENCES policy_documents(doc_id),
    model_version     TEXT        NOT NULL,
    rubric_version    TEXT        NOT NULL,
    prompt_version    TEXT        NOT NULL,
    temperature       REAL        NOT NULL,
    training_cutoff   DATE        NOT NULL,  -- chong contamination (docs/14 §3.1.4)

    gpr_salience      DOUBLE PRECISION NOT NULL,  -- [0,1], trung binh co trong so
    gpr_salience_max  DOUBLE PRECISION NOT NULL,  -- doan dam dac nhat
    channel           TEXT,                       -- energy|trade|financial|military|NULL
    direction         TEXT        NOT NULL,       -- risk_up|risk_down|neutral
    binding           BOOLEAN     NOT NULL,
    evidence          TEXT,
    rationale         TEXT,
    n_chunks          INTEGER     NOT NULL,

    -- Kiem soat chat luong TU DONG (khong doi nguoi cham tay).
    evidence_check    TEXT        NOT NULL,  -- exact|partial|missing|empty
    judge_agree       BOOLEAN,               -- LLM tham dinh (NULL = chua chay)
    judge_problem     TEXT,
    judge_salience    DOUBLE PRECISION,
    judge_note        TEXT,

    scored_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, model_version, rubric_version, prompt_version)
);
CREATE INDEX IF NOT EXISTS ix_policy_scores_quality
    ON policy_gpr_scores(evidence_check, judge_agree);

-- Hang DUNG DUOC: trich dan co that VA (chua tham dinh HOAC tham dinh dong y).
-- Loc o day mot lan de moi cho tieu thu khong tu bia dieu kien rieng.
CREATE OR REPLACE VIEW policy_gpr_scores_clean AS
SELECT s.*, d.published_at, d.doc_type, d.url
FROM policy_gpr_scores s
JOIN policy_documents d USING (doc_id)
WHERE s.evidence_check IN ('exact', 'partial', 'empty')
  AND (s.judge_agree IS NULL OR s.judge_agree);
