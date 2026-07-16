-- 001_schema_core.sql — Chân A + hạ tầng chung
-- Chạy đầu tiên. Idempotent (IF NOT EXISTS).

-- Chuỗi thời gian ngoài: GPR, GPRC, Oil, DXY, VIX, VN-Index... dạng long.
--
-- QUY TẮC VINTAGE (docs/08 §4.7/§7.1, docs/09 §2.8): `date` là ngày QUAN SÁT, KHÔNG phải
-- thời điểm dữ liệu được biết. Backtest chỉ được dùng một dòng khi `available_at <= decision_time`.
-- Dùng `date` làm proxy cho available_at = look-ahead bias. GPR daily publish trễ ~1 ngày;
-- GPRC monthly publish đầu tháng sau — chênh lệch này đủ để bịa ra alpha không tồn tại.
CREATE TABLE IF NOT EXISTS ext_series (
    series_id      TEXT             NOT NULL,   -- 'GPRD','GPRD_ACT','GPRC_VNM','BRENT','DXY','VIX','VNINDEX'...
    date           DATE             NOT NULL,   -- ngày quan sát (KHÔNG dùng để lọc backtest)
    value          DOUBLE PRECISION,
    freq           VARCHAR(10)      NOT NULL DEFAULT 'daily',  -- daily|monthly
    source         TEXT,                                       -- 'gpr_daily_file','fred','yfinance','beaverx'
    available_at   TIMESTAMPTZ      NOT NULL,   -- thời điểm SỚM NHẤT dữ liệu này biết được. Cổng chống leakage.
    revised_at     TIMESTAMPTZ,                 -- nếu nguồn revise giá trị đã publish
    source_version TEXT,                        -- version/vintage của file nguồn (vd 'gpr_export_202607')
    data_version   TEXT             NOT NULL DEFAULT 'v1',     -- FK mềm -> data_versions.label
    quality_flag   TEXT,                        -- NULL=ok; 'partial_coverage','imputed','suspect'...
    loaded_at      TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, date, data_version)
);
CREATE INDEX IF NOT EXISTS ix_ext_series_date ON ext_series(date);
-- Index chính cho truy vấn backtest: "mọi thứ biết được tính đến decision_time".
CREATE INDEX IF NOT EXISTS ix_ext_series_available ON ext_series(series_id, available_at);

-- Chỉ số tính ra: VN-GPR, S-GPR, Surprise, divergence... (dùng chung mọi chân)
CREATE TABLE IF NOT EXISTS gpr_indices (
    index_name  TEXT             NOT NULL,   -- 'VN_GPR','S_GPR_US_CN','SURPRISE','EARLY_WARN'...
    freq        VARCHAR(10)      NOT NULL,
    date        DATE             NOT NULL,
    value       DOUBLE PRECISION,
    zscore      DOUBLE PRECISION,
    pct_rank    DOUBLE PRECISION,            -- percentile rolling 1Y
    version     VARCHAR(20)      NOT NULL DEFAULT 'v1',
    computed_at TIMESTAMPTZ      NOT NULL DEFAULT now(),
    PRIMARY KEY (index_name, freq, date, version)
);
CREATE INDEX IF NOT EXISTS ix_gpr_indices_date ON gpr_indices(date);

-- Chất lượng coverage của từng index theo ngày (docs/08 §4.11, §7.3).
-- Lý do: index = Σs_i/N_t. Nếu crawler hỏng hoặc thiếu nguồn thì N_t sai → index sai,
-- nhưng chuỗi vẫn "trông bình thường". Ngày thiếu coverage phải bị gắn cờ, không im lặng tính như thường.
-- Chủ yếu phục vụ corpus VN (V-phase); với nguồn published (GPR) thì coverage do nhà cung cấp đảm bảo.
CREATE TABLE IF NOT EXISTS index_quality (
    index_name             TEXT    NOT NULL,
    date                   DATE    NOT NULL,
    source_coverage_count  INTEGER,            -- số nguồn thực tế có bài hôm đó
    expected_article_count INTEGER,            -- kỳ vọng theo baseline lịch sử
    crawl_completeness     DOUBLE PRECISION,   -- thực tế / kỳ vọng, [0,1]
    duplicate_cluster_count INTEGER,
    effective_article_count INTEGER,           -- sau dedup theo event cluster
    missing_source_flag    BOOLEAN NOT NULL DEFAULT false,
    quality_flag           TEXT,               -- NULL=ok; 'low_coverage','source_gap','suspect'
    data_version           TEXT    NOT NULL DEFAULT 'v1',
    PRIMARY KEY (index_name, date, data_version)
);
CREATE INDEX IF NOT EXISTS ix_index_quality_date ON index_quality(date);

-- Sổ version dữ liệu — mọi kết quả nghiên cứu tham chiếu về đây.
CREATE TABLE IF NOT EXISTS data_versions (
    version_id  SERIAL PRIMARY KEY,
    label       TEXT UNIQUE NOT NULL,        -- 'gpr_2026-06-29','corpus_2026-07'...
    description TEXT,
    git_commit  VARCHAR(40),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
