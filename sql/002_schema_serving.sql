-- 002_schema_serving.sql — Chân B serving: statements/statement_scores/ladder_state
-- + news_assessment (audit trail cho pipeline "1 tin vào -> 1 kết quả ra").
-- Chạy sau 001_schema_core.sql. Idempotent (IF NOT EXISTS).

-- Bảng gốc theo docs/00_engine_design.md §6. `text` KHÔNG NULL vì statement
-- rỗng là lỗi input (Statement.__post_init__ ở statement_scorer.py raise cùng
-- điều kiện phía Python — DB giữ ràng buộc y hệt, không tin caller).
CREATE TABLE IF NOT EXISTS statements (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT            NOT NULL,   -- ungdc, bis, whitehouse, mofa_cn, truth_social...
    url             TEXT,
    published_at    TIMESTAMPTZ     NOT NULL,   -- đến PHÚT với nguồn daily (CLAUDE.md #5)
    speaker         TEXT            NOT NULL,
    speaker_role    VARCHAR(40)     NOT NULL,
    speaker_country CHAR(3),
    text            TEXT            NOT NULL,
    lang            CHAR(2)         NOT NULL DEFAULT 'en',
    cadence         VARCHAR(10)     NOT NULL DEFAULT 'daily',  -- daily|slow
    inserted_at     TIMESTAMPTZ     NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_statements_published_at ON statements(published_at);
CREATE INDEX IF NOT EXISTS ix_statements_source_published
    ON statements(source, published_at);

-- Mở rộng statement_scores của docs/00 §6: doc gốc chỉ liệt kê
-- (v, target_country, channel, commitment, specificity, model_version,
-- rubric_version) — thiếu các trường mà scoring/statement_scorer.py
-- (SCORE_COLUMNS) thực sự sinh ra. Bổ sung actor_country (bắt buộc cho
-- S-GPR pair_key), rationale, encoder_p, prompt_version, temperature,
-- training_cutoff (contamination guard, docs/14 §3.1.4), content_hash (khóa
-- cache — statement_scorer.content_hash()).
CREATE TABLE IF NOT EXISTS statement_scores (
    statement_id     BIGINT          NOT NULL REFERENCES statements(id),
    v                REAL            NOT NULL,
    actor_country    CHAR(3),
    target_country   CHAR(3),
    channel          VARCHAR(20),
    commitment       VARCHAR(20)     NOT NULL,
    specificity      REAL            NOT NULL,
    rationale        TEXT,
    encoder_p        REAL,
    model_version    VARCHAR(30)     NOT NULL,
    rubric_version   VARCHAR(10)     NOT NULL,
    prompt_version   VARCHAR(10)     NOT NULL,
    temperature      REAL            NOT NULL,
    training_cutoff  DATE            NOT NULL,
    content_hash     VARCHAR(16)     NOT NULL,
    scored_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (statement_id, model_version, rubric_version)
);
-- Truy vấn chính của pipeline: lịch sử MỘT CẶP actor->target tính đến một mốc
-- thời gian (news_pipeline.process_news_item_live nạp qua statements.published_at).
CREATE INDEX IF NOT EXISTS ix_statement_scores_pair
    ON statement_scores(actor_country, target_country);

-- Trạng thái Escalation Ladder theo cặp — docs/00 §6, khớp econometrics/ladder.py.
CREATE TABLE IF NOT EXISTS ladder_state (
    pair            VARCHAR(7)      NOT NULL,   -- 'USA>CHN' (indices.s_gpr.pair_key)
    date            DATE            NOT NULL,
    state           SMALLINT        NOT NULL,
    days_in_state   INTEGER         NOT NULL,
    config_version  VARCHAR(10)     NOT NULL,
    computed_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (pair, date, config_version)
);

-- Audit trail của pipeline/news_pipeline.py — MỘT hàng cho mỗi tin đã xử lý
-- xong, giữ nguyên văn bản 3 tầng đã compose (measurement/macro/VN) kèm
-- version để không ai đọc nhầm output cũ với spec mới (CLAUDE.md #4).
-- Không có trong docs/00 §6 gốc — thêm cho pipeline production, không phải
-- tài liệu nghiên cứu.
CREATE TABLE IF NOT EXISTS news_assessment (
    id                     BIGSERIAL       PRIMARY KEY,
    statement_id           BIGINT          NOT NULL REFERENCES statements(id),
    generated_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    gamma_channel_used     VARCHAR(10),     -- 'pooled'|'act'|'threat'|NULL (xem gamma_lookup.py)
    transmission_channel   VARCHAR(20),     -- 'energy'|'trade'|'financial'|'military'|NULL
    s_gpr_now              REAL,
    s_gpr_prev             REAL,
    s_gpr_pctile           REAL,
    ladder_state           SMALLINT,
    measurement_card       TEXT            NOT NULL,
    macro_brief            TEXT            NOT NULL,
    vn_note                TEXT            NOT NULL,
    gamma_data_version     TEXT,
    git_commit             VARCHAR(40),
    kafka_topic            TEXT,
    kafka_published_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_news_assessment_statement ON news_assessment(statement_id);
CREATE INDEX IF NOT EXISTS ix_news_assessment_generated ON news_assessment(generated_at);
