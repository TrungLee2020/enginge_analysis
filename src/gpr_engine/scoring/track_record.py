"""track_record.py — M7: cham diem du bao da phat, LICH SU CONG KHAI. 🏭 production-path

docs/11 §0 R2 · §11 bang metric · docs/14 §4 muc 3d · docs/15 §1 tang 4.

R2 nguyen van: "Track record cong khai tu ngay dau. Cong bo phan phoi, cham bang
CRPS (lien tuc) va Brier (nhi phan), lich su mo. Thu duy nhat xay duoc uy tin cho
nha mo hinh chua co thuong hieu — va la thu doi thu co thuong hieu de mat se
khong lam."

BA QUY TAC LAM CHO TRACK RECORD CO NGHIA (khong co chung thi no la marketing):

1. **GHI TRUOC, CHAM SAU.** Du bao phai duoc ghi voi `issued_at` TRUOC khi ket
   cuc ton tai. `record()` tu choi mot du bao co `target_date <= issued_at` —
   cham diem thu minh viet sau khi biet ket qua la tu lua.

2. **KHONG XOA, KHONG SUA.** Mot khi da ghi, ban ghi bat bien. `resolve()` chi
   THEM ket cuc, khong duoc doi phan phoi. Track record cho phep sua la track
   record khong ton tai. `_frozen` chan viec ghi de.

3. **LUON CO BASELINE.** CRPS mot minh khong doc duoc: 0.8 la tot hay te? Chi co
   nghia khi so voi baseline VO DIEU KIEN (phan phoi lich su khong dung thong tin
   gi cua hom nay). `skill_score` = 1 − CRPS/CRPS_baseline; > 0 moi la co gia tri.
   docs/11 §11 dat nguong: CRPS < baseline.

PIT (probability integral transform): neu phan phoi du bao DUNG thi PIT ~ U(0,1).
Histogram PIT lech -> model tu tin qua (chum giua) hoac qua rong (chum bien). Day
la kiem tra HIEU CHUAN, doc lap voi do chinh xac.

⚠️ Tran claim khong doi vi co track record: track thang VAN chua co holdout
(`g0` §2), nen `predictive, chua xac nhan holdout` giu nguyen. Track record do
hieu nang TREN DU LIEU DA PHAT, khong thay the holdout.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


class TrackRecordViolation(Exception):
    """Vi pham mot trong ba quy tac — chan cung, khong canh bao."""


# ---------------------------------------------------------------------------
# Cham diem
# ---------------------------------------------------------------------------
def crps_ensemble(forecast: Sequence[float], observed: float) -> float:
    """CRPS cho phan phoi bieu dien bang MAU (ensemble/quantile draws).

        CRPS = E|X − y| − ½·E|X − X'|

    Dang nay khong can gia dinh ho phan phoi — hop voi output cua ta (quantile
    regression cho mot bo tau, khong phai mot phan phoi tham so).

    Don vi = don vi cua y; NHO HON la TOT HON. Mot minh no khong doc duoc — luon
    bao cao kem `skill_score` so voi baseline (quy tac 3).
    """
    x = np.asarray([v for v in forecast if np.isfinite(v)], dtype=float)
    if x.size == 0:
        raise ValueError("forecast rỗng — không chấm được.")
    if not np.isfinite(observed):
        raise ValueError("observed không hữu hạn.")
    term1 = float(np.mean(np.abs(x - observed)))
    # E|X − X'| bang cach vector hoa; n nho (5-20 quantile) nen O(n²) khong sao.
    term2 = float(np.mean(np.abs(x[:, None] - x[None, :])))
    return term1 - 0.5 * term2


def brier(prob: float, occurred: bool) -> float:
    """Brier cho su kien nhi phan: (p − o)². Nho hon la tot hon."""
    if not 0.0 <= prob <= 1.0:
        raise ValueError(f"prob={prob} ngoài [0,1].")
    return float((prob - (1.0 if occurred else 0.0)) ** 2)


def pit_value(forecast: Sequence[float], observed: float) -> float:
    """PIT = F̂(y) uoc luong bang ty le mau <= y. Phan phoi dung -> PIT ~ U(0,1)."""
    x = np.asarray([v for v in forecast if np.isfinite(v)], dtype=float)
    if x.size == 0:
        raise ValueError("forecast rỗng.")
    return float(np.mean(x <= observed))


def skill_score(crps_model: float, crps_baseline: float) -> float:
    """1 − CRPS/CRPS_baseline. >0 = tốt hơn baseline; 0 = ngang; <0 = tệ hơn.

    Baseline PHAI la phan phoi VO DIEU KIEN (lich su, khong dung thong tin cua
    hom nay). Lay baseline "de thang" la cach pho bien nhat de mot track record
    trong dep ma khong co gia tri.
    """
    if crps_baseline <= 0:
        raise ValueError(
            f"crps_baseline={crps_baseline} <= 0 — baseline hoàn hảo là dấu hiệu "
            "baseline dựng sai (thường là đã dùng dữ liệu tương lai).")
    return 1.0 - crps_model / crps_baseline


# ---------------------------------------------------------------------------
# So ghi
# ---------------------------------------------------------------------------
@dataclass
class Forecast:
    """Mot du bao DA PHAT. Bat bien sau khi ghi (quy tac 2)."""
    forecast_id: str
    issued_at: pd.Timestamp
    target_date: pd.Timestamp
    outcome_name: str
    quantiles: dict[str, float]              # {"0.10": ..., "0.50": ...}
    baseline_quantiles: dict[str, float]
    threshold: float | None = None           # cho Brier
    prob_threshold: float | None = None      # P(y < threshold) model noi
    baseline_prob: float | None = None
    model_version: str = ""
    data_version: str = ""
    claim: str = "predictive, chưa xác nhận holdout"
    # Dien khi ket cuc quan sat duoc:
    observed: float | None = None
    resolved_at: pd.Timestamp | None = None

    def __post_init__(self) -> None:
        self.issued_at = pd.Timestamp(self.issued_at)
        self.target_date = pd.Timestamp(self.target_date)
        if self.target_date <= self.issued_at:
            raise TrackRecordViolation(
                f"target_date={self.target_date} <= issued_at={self.issued_at}. "
                "Dự báo phải được ghi TRƯỚC khi kết cục tồn tại (quy tắc 1) — "
                "chấm điểm thứ mình viết sau khi biết kết quả là tự lừa.")
        if not self.quantiles:
            raise TrackRecordViolation("quantiles rỗng — không có gì để chấm.")
        if not self.baseline_quantiles:
            raise TrackRecordViolation(
                "baseline_quantiles rỗng. CRPS một mình không đọc được: 0.8 là "
                "tốt hay tệ? Chỉ có nghĩa khi so với baseline vô điều kiện "
                "(quy tắc 3, docs/11 §11).")

    @property
    def resolved(self) -> bool:
        return self.observed is not None

    def score(self) -> dict:
        """Cham diem — chi goi duoc khi da co ket cuc."""
        if not self.resolved:
            raise TrackRecordViolation(
                f"{self.forecast_id} chưa có kết cục (`observed`). Chấm một dự báo "
                "chưa tới hạn là chấm điều chưa xảy ra.")
        fc = list(self.quantiles.values())
        bl = list(self.baseline_quantiles.values())
        c_model = crps_ensemble(fc, self.observed)
        c_base = crps_ensemble(bl, self.observed)
        out = {
            "forecast_id": self.forecast_id,
            "outcome": self.outcome_name,
            "issued_at": self.issued_at,
            "target_date": self.target_date,
            "observed": float(self.observed),
            "crps": c_model,
            "crps_baseline": c_base,
            "skill_score": skill_score(c_model, c_base),
            "pit": pit_value(fc, self.observed),
            "brier": None,
            "brier_baseline": None,
        }
        if self.threshold is not None and self.prob_threshold is not None:
            occurred = bool(self.observed < self.threshold)
            out["brier"] = brier(self.prob_threshold, occurred)
            if self.baseline_prob is not None:
                out["brier_baseline"] = brier(self.baseline_prob, occurred)
        return out


@dataclass
class TrackRecord:
    """So ghi du bao. Append-only; `resolve` chi THEM ket cuc (quy tac 2)."""
    path: Path | None = None
    _items: dict[str, Forecast] = field(default_factory=dict)

    def record(self, fc: Forecast) -> Forecast:
        if fc.forecast_id in self._items:
            raise TrackRecordViolation(
                f"forecast_id {fc.forecast_id!r} đã tồn tại. Sổ ghi là APPEND-ONLY "
                "(quy tắc 2) — track record cho phép sửa là track record không "
                "tồn tại. Dùng id mới nếu muốn phát bản khác.")
        self._items[fc.forecast_id] = fc
        return fc

    def resolve(self, forecast_id: str, observed: float,
                resolved_at: pd.Timestamp | None = None) -> Forecast:
        """Điền kết cục. KHÔNG cho sửa lại một dự báo đã resolve."""
        if forecast_id not in self._items:
            raise KeyError(f"Không có dự báo {forecast_id!r}.")
        fc = self._items[forecast_id]
        if fc.resolved:
            raise TrackRecordViolation(
                f"{forecast_id} đã có kết cục {fc.observed}. Ghi đè kết cục = sửa "
                "lịch sử (quy tắc 2).")
        fc.observed = float(observed)
        fc.resolved_at = pd.Timestamp(resolved_at or pd.Timestamp.now("UTC"))
        return fc

    def __len__(self) -> int:
        return len(self._items)

    @property
    def pending(self) -> list[Forecast]:
        return [f for f in self._items.values() if not f.resolved]

    def scoreboard(self) -> pd.DataFrame:
        """Bảng điểm mọi dự báo ĐÃ resolve. Rỗng nếu chưa cái nào tới hạn."""
        rows = [f.score() for f in self._items.values() if f.resolved]
        cols = ["forecast_id", "outcome", "issued_at", "target_date", "observed",
                "crps", "crps_baseline", "skill_score", "pit", "brier",
                "brier_baseline"]
        return pd.DataFrame(rows, columns=cols)

    def summary(self) -> dict:
        """Tổng hợp — MỌI dự báo đã resolve đều vào, không lọc.

        Lọc bớt ô xấu khỏi tổng hợp là cách hỏng đặc trưng của track record; ở
        đây `n_resolved` và `n_pending` luôn báo cùng nhau để thấy ngay nếu có
        dự báo bị bỏ quên không resolve.
        """
        sb = self.scoreboard()
        if sb.empty:
            return {"n_total": len(self._items), "n_resolved": 0,
                    "n_pending": len(self.pending)}
        out = {
            "n_total": len(self._items),
            "n_resolved": int(len(sb)),
            "n_pending": len(self.pending),
            "crps_mean": float(sb["crps"].mean()),
            "crps_baseline_mean": float(sb["crps_baseline"].mean()),
            "skill_mean": float(sb["skill_score"].mean()),
            "beats_baseline_share": float((sb["skill_score"] > 0).mean()),
            "pit_mean": float(sb["pit"].mean()),
        }
        br = sb["brier"].dropna()
        if len(br):
            out["brier_mean"] = float(br.mean())
            bb = sb["brier_baseline"].dropna()
            if len(bb):
                out["brier_baseline_mean"] = float(bb.mean())
        return out

    def pit_histogram(self, bins: int = 10) -> pd.DataFrame:
        """Histogram PIT — kiểm HIỆU CHUẨN, độc lập với độ chính xác.

        Phân phối đúng -> PIT phẳng. Chụm giữa = model quá rộng (thiếu tự tin);
        chụm ở hai biên = quá hẹp (tự tin quá, đuôi mỏng hơn thực tế). Cột
        `expected` cho biết mức phẳng là bao nhiêu để so bằng mắt.
        """
        sb = self.scoreboard()
        if sb.empty:
            return pd.DataFrame(columns=["bin_left", "bin_right", "count", "expected"])
        counts, edges = np.histogram(sb["pit"].to_numpy(), bins=bins, range=(0.0, 1.0))
        return pd.DataFrame({
            "bin_left": edges[:-1], "bin_right": edges[1:],
            "count": counts, "expected": len(sb) / bins,
        })

    # -- luu tru: JSONL append-only ------------------------------------------
    def save(self, path: Path | str | None = None) -> Path:
        """Ghi JSONL. Lịch sử công khai phải ở dạng đọc được, không phải pickle."""
        target = Path(path or self.path or "")
        if not str(target):
            raise ValueError("Chưa có đường dẫn để lưu.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for fc in self._items.values():
                d = asdict(fc)
                for k in ("issued_at", "target_date", "resolved_at"):
                    d[k] = None if d[k] is None else pd.Timestamp(d[k]).isoformat()
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        return target

    @classmethod
    def load(cls, path: Path | str) -> TrackRecord:
        tr = cls(path=Path(path))
        p = Path(path)
        if not p.exists():
            return tr
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            observed, resolved_at = d.pop("observed"), d.pop("resolved_at")
            fc = Forecast(**d)
            if observed is not None:
                fc.observed = float(observed)
                fc.resolved_at = pd.Timestamp(resolved_at)
            tr._items[fc.forecast_id] = fc
        return tr


def unconditional_baseline(history: pd.Series,
                           taus: Iterable[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
                           as_of: pd.Timestamp | None = None) -> dict[str, float]:
    """Baseline VO DIEU KIEN: phan vi lich su TINH DEN `as_of`.

    Khong dung thong tin gi cua hom nay — do la dinh nghia. Cat theo `as_of` la
    bat buoc: phan vi tren toan mau se chua tuong lai va baseline tro nen "kho
    thang" mot cach gia tao, lam skill score cua ta trong te hon thuc te (va lan
    sau se co nguoi "sua" bang cach bo cat — nen cat o day, khong o caller).
    """
    h = history.dropna()
    if as_of is not None:
        h = h.loc[h.index <= pd.Timestamp(as_of)]
    if len(h) < 20:
        raise ValueError(
            f"Chỉ {len(h)} quan sát lịch sử tính đến {as_of} — không đủ dựng "
            "baseline phân vị đáng tin.")
    return {f"{t:.2f}": float(h.quantile(t)) for t in taus}
