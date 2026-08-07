"""guard.py — GUARD P1: mọi số trong narrative phải truy về payload. 🏭 production-path

docs/11 §1 P1 · docs/12 §5.4 · docs/15 §0 (LLM viết narrative TỪ payload đã tính).

Vì sao tồn tại — TIỀN LỆ CÓ THẬT trong chính repo này: `run_e1_diagnosis` từng
viết "~1.8×" trong khi payload là 2.77×. Không ai thấy cho tới khi soi lại. Với
tầng 4 có LLM viết văn, rủi ro đó không còn là tai nạn hiếm mà là chế độ hỏng
MẶC ĐỊNH: mô hình ngôn ngữ sinh số trôi chảy hơn là tra số.

Trước đây guard chỉ tồn tại dưới dạng test rời cho từng script (E1b, E1c, T2-full),
mỗi cái tự chép lại logic tách token. Module này là bản DÙNG CHUNG, và quan trọng
hơn: nó chạy được ở RUNTIME (chặn trước khi phát), không chỉ ở CI.

Ba thứ guard KHÔNG làm, để không tạo cảm giác an toàn giả:
  - không kiểm số có ĐÚNG không, chỉ kiểm có TRUY VỀ payload không. Payload sai
    thì narrative sai theo và guard im lặng — đó là việc của test tính toán.
  - không hiểu ngữ nghĩa: "tăng 5%" khi payload nói giảm 5% vẫn lọt. Xem
    `shock_axis.check_component_labelling` cho lớp NHÃN.
  - không bắt số bị BỎ SÓT (payload có mà narrative không nhắc).
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

# Pattern KHÔNG phải "số kết quả" — gỡ trước khi soi. Thứ tự có ý nghĩa.
_STRIP = (
    # Định danh trong code span: hash, commit, và TÊN FILE report
    # (`t2_full_holm_f2579b30928f.csv`). Bản đầu chỉ khớp hash hex TRẦN
    # (`[0-9a-f]{6,}`) nên tên file lọt qua: hash bên trong bị regex "mốc năm"
    # bên dưới cắt mất 4 chữ số đầu, phần đuôi `30928` thành token số vô chủ và
    # guard chặn MỌI tin — `news_pipeline` truyền chính tên file γ làm
    # `data_version`, nên đường serving sống không chạy nổi một tin nào.
    # Điều kiện "có ít nhất một chữ cái/gạch dưới, KHÔNG chứa khoảng trắng" giữ
    # nguyên răng của guard: `2.77` trong backtick vẫn bị kiểm, văn xuôi mang số
    # nhét vào backtick cũng vậy — chỉ định danh một token mới được miễn.
    r"`[\w.\-/]*[A-Za-z_][\w.\-/]*`",
    r"\d{4}-\d{2}-\d{2}[T0-9:]*",   # ngày ISO
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b",  # giờ 14:07 — timestamp, không phải kết quả
    # Ngày dd/mm[/yyyy]. Tháng phải ≤12 nên "23/72 ô" (tỉ lệ THẬT, phải kiểm)
    # không lọt vào đây — đó là lý do không dùng `\d+/\d+` cho gọn.
    r"\b(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])(?:/\d{2,4})?\b",
    r"docs?/\d+",                   # docs/11, doc/14
    r"§\s*[\d.]+",                  # §5.4
    r"DEC-\d{4}-\d{2}-\d{2}[\w-]*",  # id quyết định
    r"KĐ-?\w*\d[\w-]*",             # KĐ8, KĐ-E1c
    r"[A-Za-zĐ]+-\d[\w-]*",         # SCA-01, E1b
    r"\d+σ",                        # 2σ, 4σ
)
# ⚠️ KHÔNG strip "p=..." — p-value LÀ một kết quả và phải truy về payload. Bản
# nháp từng có `\bp=\d` để "bỏ nhãn", nó cắt mất chữ số đầu rồi phần đuôi
# ".0173" bị đọc thành 173 và guard báo sai. Nhãn không cần gỡ; số phải kiểm.

# Hằng số cấu hình được phép xuất hiện mà không cần nằm trong payload.
DEFAULT_ALLOWED = frozenset({0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 100.0,
                             0.05, 0.10, 0.90, 0.95, 0.99})


class GuardViolation(Exception):
    """Narrative chứa số không truy được về payload — CHẶN, không cảnh báo.

    Cảnh báo thì bay lên stderr rồi mất, còn văn bản vẫn phát. Đây là loại lỗi
    phải chặn cứng: một con số bịa trong brief làm hỏng toàn bộ track record.
    """


@dataclass(frozen=True)
class GuardReport:
    ok: bool
    unmatched: tuple[str, ...] = ()
    n_checked: int = 0
    allowed_size: int = 0
    detail: str = ""


def _flatten(obj, out: list[float]) -> None:
    """Gom mọi số trong payload lồng nhau (dict/list/scalar).

    Bỏ qua NaN/inf: chúng không phải giá trị hiển thị được, và `int(nan)` ném
    ValueError. Payload chứa NaN là chuyện bình thường (ô chưa tính được) —
    guard không được sập vì nó, chỉ đơn giản là không có gì để đối chiếu.
    """
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(obj):
            out.append(float(obj))
    elif isinstance(obj, Mapping):
        for v in obj.values():
            _flatten(v, out)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _flatten(v, out)


def payload_values(payload, extra_allowed: Iterable[float] = ()) -> list[float]:
    """Mọi số hữu hạn trong payload + hằng số cấu hình cho phép.

    Trả LIST thô (không phải tập đã làm tròn) vì việc đối chiếu cần biết độ chính
    xác mà narrative HIỂN THỊ — xem `_matches`.
    """
    raw: list[float] = []
    _flatten(payload, raw)
    return [*DEFAULT_ALLOWED, *(float(x) for x in extra_allowed), *raw]


def _decimals(token: str) -> int:
    """Số chữ số thập phân mà narrative hiển thị."""
    tok = token.replace(",", ".")
    return len(tok.split(".")[1]) if "." in tok else 0


def _matches(token: str, values: Iterable[float]) -> bool:
    """Token có phải là một giá trị payload ĐÃ LÀM TRÒN KHI HIỂN THỊ không?

    Đây là điểm tinh tế nhất của guard. Payload lưu p=0.017281, narrative in
    "0.017" — đó là hiển thị trung thực, KHÔNG phải bịa. Bản đầu so bằng tập giá
    trị làm tròn cứng 4 chữ số nên báo sai hàng loạt số đúng, và cách sửa sai
    lầm là nới ngưỡng (rồi guard mất tác dụng).

    Cách đúng: làm tròn giá trị payload về ĐÚNG độ chính xác mà token hiển thị,
    rồi so. Dung sai vừa khít với cái mắt người đọc thấy — không thể biến 1.8
    thành 2.77, nhưng chấp nhận 0.017 cho 0.017281.

    Hai dạng hiển thị đều thử: x (nguyên bản) và x*100 (tỉ lệ in ra phần trăm).
    """
    val = float(token.replace(",", "."))
    d = _decimals(token)
    for v in values:
        if round(v, d) == val or round(v * 100.0, d) == val:
            return True
    return False


def extract_numbers(text: str, skip_tables: bool = True) -> list[str]:
    """Token số trong văn xuôi. `skip_tables=True` bỏ dòng bảng markdown.

    Bảng thường in thẳng từ DataFrame — kiểm chúng thuộc về test tính toán, không
    phải guard narrative. Bật `skip_tables=False` nếu bảng do tay dựng.
    """
    lines = text.splitlines()
    if skip_tables:
        lines = [ln for ln in lines if not ln.lstrip().startswith("|")]
    body = "\n".join(lines)
    for pat in _STRIP:
        body = re.sub(pat, " ", body)
    # Mốc năm đơn (1990, 2021). Lookahead phải là `[.,]\d` chứ KHÔNG phải `[.\d]`:
    # với `[.\d]` thì "2021." cuối câu không được gỡ (dấu chấm hết câu bị nhầm là
    # dấu thập phân) và guard báo sai mọi năm đứng cuối câu.
    body = re.sub(r"(?<![.,\d])\d{4}(?![.,]\d)(?!\d)", " ", body)
    return NUM_RE.findall(body)


def check_narrative(
    text: str | Iterable[str],
    payload,
    extra_allowed: Iterable[float] = (),
    skip_tables: bool = True,
) -> GuardReport:
    """Soi narrative. Trả GuardReport — KHÔNG raise (dùng `enforce` để chặn)."""
    body = text if isinstance(text, str) else "\n".join(text)
    allowed = payload_values(payload, extra_allowed)
    toks = extract_numbers(body, skip_tables=skip_tables)
    bad = [t for t in toks if not _matches(t, allowed)]
    return GuardReport(
        ok=not bad, unmatched=tuple(bad), n_checked=len(toks),
        allowed_size=len(allowed),
        detail="" if not bad else
        f"{len(bad)} số không truy được về payload: {bad}")


def enforce(
    text: str | Iterable[str],
    payload,
    extra_allowed: Iterable[float] = (),
    skip_tables: bool = True,
) -> str:
    """Như `check_narrative` nhưng RAISE khi vi phạm. Dùng ở cửa phát văn bản."""
    rep = check_narrative(text, payload, extra_allowed, skip_tables)
    if not rep.ok:
        raise GuardViolation(
            f"Guard P1: {rep.detail}. Mọi số trong narrative phải tính từ payload "
            "rồi tham chiếu — thêm trường vào payload, đừng gõ tay (docs/12 §5.4). "
            "Tiền lệ có thật: report từng ghi '1.8×' trong khi payload là 2.77×.")
    return text if isinstance(text, str) else "\n".join(text)


@dataclass
class NarrativeBuilder:
    """Gom narrative rồi guard MỘT LẦN ở cuối — cửa duy nhất văn bản đi ra.

    Dùng cho composer tầng 4: `add()` từng đoạn, `render()` chạy guard rồi mới
    trả chuỗi. Quên gọi guard là không thể, vì `render` là cách duy nhất lấy text.
    """
    payload: object
    extra_allowed: tuple[float, ...] = ()
    skip_tables: bool = True
    _parts: list[str] = field(default_factory=list)

    def add(self, line: str) -> NarrativeBuilder:
        self._parts.append(line)
        return self

    def add_table(self, markdown: str) -> NarrativeBuilder:
        self._parts.append(markdown)
        return self

    def render(self) -> str:
        return enforce("\n".join(self._parts), self.payload,
                       self.extra_allowed, self.skip_tables)
