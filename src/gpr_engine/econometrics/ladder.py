"""ladder.py — Escalation Ladder V1: may trang thai cap quoc gia, RULE-BASED.

Spec: docs/00 §4.1. 5 trang thai:
    S0 binh thuong -> S1 khau chien -> S2 de doa -> S3 chuan bi/dong vien -> S4 hanh dong

V1 rule-based CO Y (minh bach, audit duoc): phan trang thai theo nguong dong
thoi cua cac chi bao (S-GPR pair, GDELT QuadClass, JUMP chan A). V2 (HMM/regime
switching) chi lam neu V1 chung minh gia tri — khong nhay coc.

BANG NGUONG NAM TRONG CONFIG VERSION-HOA (config/ladder_v1.yaml), khong hard-
code trong ham. `config_version` di theo tung hang output (schema `ladder_state`
docs/00 §6) — doi nguong la doi version, hai run khac config khong tron lan.

Dau vao la cac cot PERCENTILE (0..100) do caller tinh bang expanding/rolling
KHONG nhin tuong lai (vd `indices.s_gpr.expanding_percentile`) — ladder chi so
sanh nguong, khong tu tinh percentile, de moi con so phat ra bat bien ve sau
(tinh than available_at, CLAUDE.md #11).

NaN = chi bao chua co du lieu -> dieu kien do KHONG thoa (conservative: thieu
bang chung thi khong leo bac). Voi dieu kien chieu "<=" dieu nay co nghia rule
ca cum khong bat duoc — ghi ro thay vi doan.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

DEFAULT_LADDER_CONFIG = Path("config/ladder_v1.yaml")
_OPS = {">", ">=", "<", "<="}
LADDER_STATES = (0, 1, 2, 3, 4)


@dataclass(frozen=True)
class LadderRule:
    """Rule cho MOT trang thai: mode='all' (VA) | 'any' (HOAC) tren conditions.

    condition = {indicator, op, value} — indicator la ten cot percentile,
    value la nguong percentile (0..100).
    """
    state: int
    mode: str
    conditions: tuple[dict, ...]


@dataclass(frozen=True)
class LadderConfig:
    version: str
    rules: tuple[LadderRule, ...]          # sap giam dan theo state

    @property
    def indicators(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.rules:
            for c in r.conditions:
                seen.setdefault(c["indicator"])
        return list(seen)


def load_ladder_config(path: str | Path = DEFAULT_LADDER_CONFIG) -> LadderConfig:
    """Doc + validate config nguong. Loi config la loi CHET (raise), khong warn."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    version = raw.get("version")
    if not version:
        raise ValueError(f"{path}: thieu 'version' — nguong phai version-hoa.")
    rules = []
    for entry in raw.get("states", []):
        state = entry.get("state")
        if state not in LADDER_STATES:
            raise ValueError(f"{path}: state={state!r} khong thuoc {LADDER_STATES}")
        mode = entry.get("mode", "all")
        if mode not in ("all", "any"):
            raise ValueError(f"{path}: mode={mode!r} phai 'all'|'any'")
        conds = entry.get("conditions", [])
        if not conds:
            raise ValueError(f"{path}: state {state} khong co condition nao.")
        for c in conds:
            if not {"indicator", "op", "value"} <= set(c):
                raise ValueError(f"{path}: condition thieu truong: {c}")
            if c["op"] not in _OPS:
                raise ValueError(f"{path}: op={c['op']!r} phai thuoc {_OPS}")
            if not 0 <= float(c["value"]) <= 100:
                raise ValueError(f"{path}: value={c['value']} ngoai [0,100] "
                                 "(nguong la percentile).")
        rules.append(LadderRule(state=int(state), mode=mode,
                                conditions=tuple(conds)))
    if not rules:
        raise ValueError(f"{path}: khong co state nao trong config.")
    rules.sort(key=lambda r: -r.state)
    return LadderConfig(version=str(version), rules=tuple(rules))


def _condition_mask(df: pd.DataFrame, cond: dict) -> pd.Series:
    ind, op, val = cond["indicator"], cond["op"], float(cond["value"])
    if ind not in df.columns:
        raise KeyError(
            f"Chi bao {ind!r} khong co trong input (co: {list(df.columns)}). "
            "Thieu chi bao la thieu DU LIEU, khong duoc lang le bo qua rule.")
    s = df[ind]
    if op == ">":
        m = s > val
    elif op == ">=":
        m = s >= val
    elif op == "<":
        m = s < val
    else:
        m = s <= val
    return m.fillna(False)          # NaN -> khong thoa (conservative)


def classify_ladder(
    indicators: pd.DataFrame,
    config: LadderConfig,
) -> pd.DataFrame:
    """Phan trang thai theo ngay cho MOT cap: state cao nhat co rule thoa.

    indicators: index=date, cot = percentile 0..100 (caller tinh, khong lookahead).
    Returns: DataFrame index=date, cot [state, days_in_state, config_version]
    (khop schema `ladder_state` docs/00 §6). Khong rule nao thoa -> S0.
    """
    if indicators.empty:
        raise ValueError("indicators rong.")
    state = pd.Series(0, index=indicators.index, dtype=int)
    assigned = pd.Series(False, index=indicators.index)
    for rule in config.rules:                    # da sap giam dan theo state
        masks = [_condition_mask(indicators, c) for c in rule.conditions]
        fired = pd.concat(masks, axis=1)
        fired = fired.all(axis=1) if rule.mode == "all" else fired.any(axis=1)
        take = fired & ~assigned
        state[take] = rule.state
        assigned |= take

    # days_in_state: so ngay lien tiep o trang thai hien tai (dem tu 1).
    change = state.ne(state.shift())
    run_id = change.cumsum()
    days = state.groupby(run_id).cumcount() + 1

    return pd.DataFrame({
        "state": state,
        "days_in_state": days,
        "config_version": config.version,
    })


def ladder_transitions(states: pd.Series) -> pd.DataFrame:
    """Cac lan CHUYEN BAC — trigger tang 4 (docs/15 §1: 'chuyen bac ladder').

    Returns: DataFrame [date, from_state, to_state, direction] voi direction
    'up' (leo thang — vd S2->S4 trong Measurement Card) | 'down'.
    """
    prev = states.shift()
    changed = states.ne(prev) & prev.notna()
    out = pd.DataFrame({
        "date": states.index[changed],
        "from_state": prev[changed].astype(int).to_numpy(),
        "to_state": states[changed].astype(int).to_numpy(),
    })
    out["direction"] = ["up" if b > a else "down"
                        for a, b in zip(out["from_state"], out["to_state"])]
    return out
