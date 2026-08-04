"""shock_axis.py — TRUC BAO CAO shock + cong may kiem tinh hop le (g0 §7.1 = A).

Quyet dinh DEC-2026-08-02-shock-axis (config/hypothesis_registry.yaml `decisions`,
ban chu ky o `g0_governance.md` §7.1):

    Bang γ chay CA BA thuoc do {LEVEL, INNOVATION, LEVEL+JUMP}, bao cao het,
    KHONG chon mot. primary_cell.shock cua SCA-01 van UNRESOLVED (cho E1c-exo).

DIEU KIEN KEM — cai lam cho quyet dinh nay khong pha CLAUDE.md #9:

    LEVEL va LEVEL+JUMP chi ELIGIBLE khi inference="lag_augmented".

Vi sao: #9 noi dua LEVEL vao hoi quy roi goi he so la "tac dong cua cu soc" la
sai khai niem — vi LEVEL gop tin moi + tin lap + phan da du bao duoc. Lag
augmentation (MO-PM 2021) them lag cua CHINH shock vao ma tran thiet ke, tuc
partial-out phan du bao duoc NGAY TRONG hoi quy; phan con lai cua regressor la
innovation. Nen he so doc duoc la phan ung voi phan BAT NGO cua level — dung cai
ma #9 doi hoi, chi khac la khu o buoc hoi quy thay vi buoc dung bien.

Bo dieu kien do di thi LEVEL quay lai la vi pham #9. Vi the cong nay la MAY, o
day, va co test khoa — khong phai mot cau trong docstring de ai do quen.
"""
from __future__ import annotations

from dataclasses import dataclass

# Ten thuoc do trong trai bao cao. Hau to cot trong panel = ten nay.
SHOCK_MEASURES = ("LEVEL", "INNOVATION", "LEVEL_PLUS_JUMP")

# Thuoc do can lag augmentation moi eligible (chua khu phan du bao duoc o buoc
# dung bien). INNOVATION da khu san nen eligible voi moi che do suy dien.
REQUIRES_LAG_AUGMENTATION = frozenset({"LEVEL", "LEVEL_PLUS_JUMP"})

DECISION_ID = "DEC-2026-08-02-shock-axis"


@dataclass(frozen=True)
class Eligibility:
    """Ket qua cong: eligible + ly do doc duoc (di thang vao report)."""
    measure: str
    inference: str
    eligible: bool
    reason: str


def gate_shock_eligibility(measure: str, inference: str) -> Eligibility:
    """Cong may cua DEC-2026-08-02-shock-axis. KHONG tu phan GO/NO-GO ket qua —
    chi tra loi "he so nay co duoc doc nhu phan ung voi cu soc khong".

    measure   : mot trong SHOCK_MEASURES.
    inference : "hac" | "lag_augmented" (che do cua run_local_projection).
    """
    if measure not in SHOCK_MEASURES:
        raise ValueError(f"measure={measure!r} khong thuoc {SHOCK_MEASURES}")
    if inference not in ("hac", "lag_augmented"):
        raise ValueError(f"inference={inference!r} khong hop le")

    if measure not in REQUIRES_LAG_AUGMENTATION:
        return Eligibility(
            measure, inference, True,
            "INNOVATION đã khử phần dự báo được ở bước dựng biến (shocks.innovation, "
            "AR(p) rolling) — eligible với mọi chế độ suy diễn.")
    if inference == "lag_augmented":
        return Eligibility(
            measure, inference, True,
            f"{measure} + lag augmentation: lag của chính shock nằm trong ma trận "
            "thiết kế, phần dự báo được bị partial-out ngay trong hồi quy "
            "(MO-PM 2021) → hệ số đọc được là phản ứng với phần BẤT NGỜ. "
            f"Điều kiện của {DECISION_ID}.")
    return Eligibility(
        measure, inference, False,
        f"{measure} với inference={inference!r}: phần đã dự báo được của level "
        "KHÔNG bị khử ở đâu cả — hệ số không đọc được là 'tác động của cú sốc' "
        f"(CLAUDE.md #9). {DECISION_ID} chỉ cho phép {measure} khi "
        "inference='lag_augmented'.")


def eligible_measures(inference: str) -> list[str]:
    """Cac thuoc do doc duoc duoi mot che do suy dien."""
    return [m for m in SHOCK_MEASURES
            if gate_shock_eligibility(m, inference).eligible]


def shock_column(prefix: str, measure: str) -> str:
    """Ten cot panel cho (kenh, thuoc do): 'GPR' + 'LEVEL' -> 'GPR_LEVEL'."""
    if measure not in SHOCK_MEASURES:
        raise ValueError(f"measure={measure!r} khong thuoc {SHOCK_MEASURES}")
    return f"{prefix}_{measure}"


# ---------------------------------------------------------------------------
# SPEC KEP (docs/16 §2.2) — cong may cho KY LUAT NHAN
# ---------------------------------------------------------------------------
# Spec kep dua CA HAI thanh phan vao cung hoi quy:
#     Δy = β_A · ANTICIPATED + β_S · SURPRISE + controls + ε
#
# No khong pha CLAUDE.md #9 nho CACH GOI TEN, khong nho cong thuc. β_A hop le khi
# goi la "phan ung voi thanh phan DA DU BAO DUOC"; goi no la "tac dong cua cu soc"
# thi vi pham #9 y het dua level tran vao hoi quy. Van ban khong chan duoc ai —
# nen quy tac o day la MAY, va report generator phai lay nhan tu day.
COMPONENT_LABELS: dict[str, str] = {
    "ANTICIPATED": "phản ứng với thành phần ĐÃ DỰ BÁO ĐƯỢC",
    "SURPRISE": "phản ứng với cú sốc (phần bất ngờ)",
}
# Tu ngu chi duoc dung cho SURPRISE. Dung cho ANTICIPATED = vi pham #9.
SHOCK_ONLY_TERMS = ("cú sốc", "shock", "bất ngờ", "surprise", "innovation")


def component_claim_label(component: str) -> str:
    """Nhan BAT BUOC cho mot thanh phan cua spec kep. Report phai dung cai nay."""
    if component not in COMPONENT_LABELS:
        raise ValueError(
            f"component={component!r} khong thuoc {tuple(COMPONENT_LABELS)}")
    return COMPONENT_LABELS[component]


def check_component_labelling(component: str, text: str) -> None:
    """Raise neu narrative goi ANTICIPATED bang tu ngu danh cho cu soc (#9).

    Dung trong report generator cua spec kep. Day la ban sao cua tinh than Guard
    P1 nhung cho NHAN thay vi cho SO: mot cau van sai nhan bien he so hop le
    thanh mot claim vi pham nguyen tac da khoa, va khong test nao khac bat duoc.
    """
    if component != "ANTICIPATED":
        return
    low = text.lower()
    hits = [t for t in SHOCK_ONLY_TERMS if t in low]
    if hits:
        raise ValueError(
            f"Narrative gọi thành phần ANTICIPATED bằng từ ngữ dành cho cú sốc: "
            f"{hits}. β_ANTICIPATED là {COMPONENT_LABELS['ANTICIPATED']} — gọi nó "
            "là tác động của cú sốc vi phạm CLAUDE.md #9 y như đưa level trần vào "
            "hồi quy (docs/16 §2.2 điều kiện 2).")
