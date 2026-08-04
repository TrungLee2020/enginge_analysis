"""vn_exposure.py — TANG 3 cho VN, nhanh DINH TINH khi chua co tham so uoc luong.

🏭 production-path. Thuan tra bang, KHONG LLM, KHONG hoi quy.

`config/params/vn.yaml` chua co muc `fitted:` (beta/theta/lambda chua uoc
luong — xem tier3_country.py) va `build_monthly_panel()` chua co cot loi suat
VN-Index that. Vi vay tang 3 cho VN trong pipeline nay CHUA THE dinh luong.
Day la hanh vi DUNG theo chinh skill gpr-macro-assessment (SKILL.md §"Khi nao
noi tôi khong biet"): "Khong co tham so uoc luong thi khong co claim dinh
luong" — module nay chuyen hoa nguyen tac do thanh code, khong bia so de lap.

Bang 4 kenh phoi nhiem chuyen tu `vietnam-params.md` §2 (skill upload cua
nguoi dung). VN gan nhu luon o vai spillover — xem `vietnam-params.md` §1.
"""
from __future__ import annotations

from dataclasses import dataclass

# Cung mien gia tri voi statement_scorer.TRANSMISSION_CHANNELS.
TRANSMISSION_CHANNELS = ("energy", "trade", "financial", "military")

CLAIM_VN_NOTE = "association"


@dataclass(frozen=True)
class VNExposure:
    """Ghi chu dinh tinh cho phan VIET NAM cua brief. KHONG co con so du bao."""
    transmission_channel: str | None
    exposure_channel: str          # ten kenh phoi nhiem VN (co the ghep nhieu)
    direction_note: str            # huong + canh bao (2 chieu neu co)
    mechanism_note: str            # co che truyen dan (Malacca, T+2.5, bien do 7%...)
    has_quant_params: bool = False  # luon False cho toi khi config/params/vn.yaml co fitted:
    claim: str = CLAIM_VN_NOTE


# vietnam-params.md §2 — 4 kenh phoi nhiem. Vai tro VN gan nhu luon spillover.
_EXPOSURE_TABLE: dict[str, VNExposure] = {
    "energy": VNExposure(
        transmission_channel="energy",
        exposure_channel="Năng lượng",
        direction_note=(
            "Giá dầu ↑ → chi phí đầu vào, lạm phát, áp lực tỷ giá tăng. "
            "Không mặc định dấu nhỏ — phụ thuộc quy mô và độ dai dẳng cú sốc."),
        mechanism_note=(
            "Sốc Trung Đông/Hormuz thường lan sang điểm nghẽn thứ cấp gồm eo "
            "Malacca (cửa ngõ thương mại VN) — kênh vật lý này không nằm trong "
            "4 biến tài chính thông thường (dầu/DXY/VIX/lãi suất Mỹ). Với nước "
            "xuất khẩu, cước vận tải/thời gian giao hàng có thể là kênh mạnh "
            "hơn giá dầu."),
    ),
    "trade": VNExposure(
        transmission_channel="trade",
        exposure_channel="Thương mại",
        direction_note=(
            "Trục Mỹ–Trung là kênh chi phối. Tác động HAI CHIỀU: rủi ro (nhu "
            "cầu xuất khẩu giảm, gián đoạn chuỗi cung ứng) LẪN cơ hội (chuyển "
            "hướng đơn hàng/sản xuất sang VN) — không mặc định dấu âm."),
        mechanism_note=(
            "Thuế quan/kiểm soát xuất khẩu → chuyển hướng đơn hàng + nhu cầu "
            "xuất khẩu; cước container đi cùng nếu chạm điểm nghẽn vận tải."),
    ),
    "financial": VNExposure(
        transmission_channel="financial",
        exposure_channel="Tài chính / tỷ giá",
        direction_note="DXY mạnh lên → áp lực USD/VND, dòng vốn có xu hướng rút.",
        mechanism_note=(
            "Trừng phạt tài chính, SWIFT, dòng vốn tránh rủi ro toàn cầu → "
            "truyền qua tỷ giá VND trước khi chạm chứng khoán."),
    ),
    "military": VNExposure(
        transmission_channel="military",
        exposure_channel="Năng lượng + Vận tải biển",
        direction_note=(
            "Hướng và độ lớn phụ thuộc mạnh vào khu vực xảy ra xung đột — "
            "không đọc một dấu chung cho mọi cú sốc quân sự."),
        mechanism_note=(
            "Xung đột vũ trang tác động VN chủ yếu gián tiếp qua giá dầu và "
            "điểm nghẽn hàng hải (Hormuz→Malacca, Biển Đỏ→Panama) hơn là qua "
            "kênh quân sự trực tiếp — VN hầu như luôn ở vai spillover."),
    ),
}

_UNMAPPED = VNExposure(
    transmission_channel=None,
    exposure_channel="chưa xác định",
    direction_note="Chưa xác định được kênh truyền dẫn cho tin này.",
    mechanism_note=(
        "Kênh chấm điểm (sanction/diplomacy/tech) chưa có ánh xạ sang kênh "
        "truyền dẫn 4 giá trị (energy/trade/financial/military) — quyết định "
        "thiết kế đang mở (docs/15 §6.3, statement_scorer.CHANNEL_TO_TRANSMISSION). "
        "Cần xem xét thủ công thay vì đoán kênh."),
)


def vn_exposure_note(transmission_channel: str | None) -> VNExposure:
    """Tra bang kenh phoi nhiem VN theo kenh truyen dan cua tin.

    `transmission_channel` la ket qua cua
    `scoring.statement_scorer.to_transmission_channel(channel)` — None nghia
    la LLM cham kenh (sanction/diplomacy/tech) chua co anh xa, tra ve ghi chu
    "chua xac dinh" thay vi doan.
    """
    if transmission_channel is None:
        return _UNMAPPED
    if transmission_channel not in TRANSMISSION_CHANNELS:
        raise ValueError(
            f"transmission_channel={transmission_channel!r} không thuộc "
            f"{TRANSMISSION_CHANNELS} | None.")
    return _EXPOSURE_TABLE[transmission_channel]
