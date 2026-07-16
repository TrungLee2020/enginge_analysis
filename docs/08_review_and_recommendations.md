# REVIEW & RECOMMENDATIONS — GPR GLOBAL ENGINE / VN-GPR

**Phiên bản:** 1.0  
**Thời điểm tổng hợp:** 07/2026  
**Phạm vi rà soát:**  
- `00_engine_design.md`
- `01_research_methodology.md`
- `02_engineering_plan.md`
- `05_build_order.md`
- `06_transmission_cascade_update.md`
- `07_formulas_reference.md`

---

# 1. TÓM TẮT ĐIỀU HÀNH

Thiết kế hiện tại có nền tảng tốt và vượt xa cách tiếp cận đơn giản kiểu:

```text
Tin tức → sentiment → dự báo thị trường
```

Điểm mạnh nhất của hệ thống là tách ba nguồn thông tin địa chính trị thành ba “chân” khác nhau:

1. **Media Attention** — báo chí đang chú ý điều gì.
2. **Primary Statements** — chủ thể quyền lực đang phát tín hiệu hoặc thể hiện ý định gì.
3. **Physical Events** — hành động hoặc sự kiện thực tế nào đã xảy ra.

Sau đó hệ thống mới kết hợp các tín hiệu này với:

- kênh truyền dẫn vĩ mô toàn cầu;
- rủi ro riêng từng quốc gia;
- mô hình kinh tế lượng;
- backtest ngoài mẫu;
- lớp serving cho BeaverX.

Kiến trúc này có tiềm năng tạo ra hai loại sản phẩm độc lập:

- **Global Macro Impact:** tác động của geopolitical shock lên Oil, DXY, VIX, US10Y và các biến toàn cầu;
- **Country Transmission:** cách các cú sốc đó truyền sang từng thị trường, trước hết là Việt Nam.

Tuy nhiên, trước khi triển khai G2, cần sửa một số vấn đề phương pháp quan trọng. Nếu không, hệ thống có thể chạy đúng về kỹ thuật nhưng đưa ra kết quả sai về nhân quả hoặc đánh giá quá cao giá trị dự báo.

Ba việc cần sửa ngay:

1. Sửa dynamic mediation và tách rõ global-direct khỏi domestic-direct.
2. Đưa decomposition `level / persistent / innovation / surprise` lên ngay G2.
3. Khóa final holdout thật sự và bổ sung `available_at` cho toàn bộ dữ liệu.

---

# 2. ĐÁNH GIÁ TỔNG THỂ

| Thành phần | Đánh giá |
|---|---|
| Định vị research gap | Tốt |
| Kiến trúc ba chân attention–intent–acts | Rất tốt |
| Thiết kế global-first | Rất tốt |
| Gate theo incremental value | Rất tốt |
| Engineering/versioning | Tốt |
| LLM validation | Khá, cần mở rộng |
| Nhận dạng geopolitical shock | Chưa đủ |
| Dynamic mediation | Cần sửa |
| Variance decomposition | Cần thay |
| Backtest governance | Cần siết chặt |
| Tiềm năng risk-monitoring | Cao |
| Tiềm năng tạo alpha | Chưa thể kết luận |
| Tiềm năng thành research paper | Có, nếu siết identification và validation |

---

# 3. NHỮNG ĐIỂM ĐANG LÀM TỐT

## 3.1. Tách ba khái niệm geopolitical khác nhau

Thiết kế hiện tại nhận ra rằng báo chí, phát ngôn chính thức và hành động thực tế không đo cùng một thứ:

```text
Media Attention  = báo chí đang tập trung vào điều gì
Primary Statement = actor quyền lực đang phát tín hiệu gì
Physical Event    = điều gì thực sự đã xảy ra
```

Đây là một đóng góp quan trọng vì các chỉ số GPR truyền thống thường trộn ba khái niệm này.

## 3.2. Tách Threat và Act

Việc tách:

```text
GPT = geopolitical threats
GPA = geopolitical acts
```

là đúng hướng vì threats và acts có thể tác động khác nhau:

- threat có thể kéo dài và được thị trường price-in dần;
- act chỉ tạo shock mạnh khi nó bất ngờ;
- act đã được dự báo trước có thể ít tác động hơn một threat mới và cụ thể.

## 3.3. Global-first, country params sau

Thiết kế:

```text
ENGINE chung
+
PARAMS riêng từng quốc gia
```

giúp tránh build một hệ thống chỉ dùng được cho Việt Nam.

Tầng 1–2 có thể được dùng cho nhiều quốc gia, trong khi tầng 3 chỉ cần ước lượng lại:

- độ nhạy dầu;
- độ nhạy USD;
- độ nhạy VIX;
- độ nhạy lãi suất Mỹ;
- rủi ro riêng quốc gia.

## 3.4. Có gate GO/NO-GO

Việc chỉ giữ chân B/C khi chúng tạo incremental value là rất tốt:

```text
A
A + B
A + C
A + B + C
A + B + C + divergence
```

Nếu một nguồn dữ liệu không cải thiện mô hình ngoài mẫu, nó nên bị loại hoặc chỉ giữ cho mục đích giải thích.

## 3.5. Có định hướng research trước, service hóa sau

Không service hóa econometrics và backtest trước khi kiểm định là quyết định đúng.

```text
Research layer: offline
Serving layer: production
```

Điều này hạn chế việc đưa một tín hiệu chưa được validate vào production.

---

# 4. VẤN ĐỀ PHƯƠNG PHÁP QUAN TRỌNG

# 4.1. Dynamic mediation hiện chưa đúng theo thời gian

Thiết kế hiện tại gần với dạng:

\[
Total_h
=
Direct_h
+
\sum_M \theta_{M,h}\gamma_{M,j,h}
\]

Trong đó:

- \(\gamma_{M,j,h}\): GPR tác động lên mediator \(M\) tại horizon \(h\);
- \(\theta_{M,h}\): mediator tác động lên thị trường tại cùng horizon \(h\).

Cách nhân hai hệ số tại cùng horizon không phản ánh đúng chuỗi động.

Ví dụ:

```text
GPR shock
→ sau 2 ngày: Oil tăng
→ sau thêm 3 ngày: VN-Index phản ứng
```

Tổng tác động xuất hiện ở ngày thứ 5, không phải bằng hệ số ngày 5 nhân hệ số ngày 5.

Công thức phù hợp hơn:

\[
\boxed{
Indirect_{j\rightarrow c}(h)
=
\sum_M
\sum_{s=0}^{h}
\gamma_{M,j}(s)
\theta^c_M(h-s)
}
\]

Đây là phép chập theo thời gian giữa:

- phản ứng của mediator sau geopolitical shock;
- phản ứng của thị trường sau mediator shock.

## Khuyến nghị

Ở phiên bản đầu, nên gọi kết quả là:

> **Dynamic transmission decomposition**

Chưa nên gọi là causal mediation cho tới khi có chiến lược nhận dạng rõ ràng.

---

# 4.2. Global-direct và domestic-direct đang bị trộn

Hiện tại `GPRC_VNM_ORTH` hoặc `GPR^{VN,\perp}` được dùng như direct shock trong tầng 3.

Nhưng biến này đã được trực giao hóa khỏi:

- global GPR;
- US GPR;
- China GPR;
- Oil hoặc các biến toàn cầu liên quan.

Theo định nghĩa:

\[
GPR^{VN,\perp}
\]

là phần riêng của Việt Nam, không phải direct effect của global shock lên Việt Nam.

Cần tách hai direct effect:

## Global direct effect

Global shock tác động trực tiếp lên tâm lý hoặc định giá tại Việt Nam mà không đi qua Oil, DXY, VIX:

\[
\beta^c_{j,h}GPR^j_t
\]

## Domestic direct effect

Rủi ro riêng Việt Nam:

\[
\lambda^c_h GPR^{c,\perp}_t
\]

Phương trình tầng 3 nên có dạng:

\[
\begin{aligned}
r^c_{t+h}
=
\alpha^c_h
&+
\sum_j \beta^c_{j,h}GPR^j_t \\
&+
\sum_M \theta^c_{M,h}M_t \\
&+
\lambda^c_h GPR^{c,\perp}_t \\
&+
\Phi^c X^c_t
+
\varepsilon^c_{t+h}
\end{aligned}
\]

Trong đó:

- \(\beta\): global-direct;
- \(\theta\): indirect qua macro;
- \(\lambda\): domestic-direct.

---

# 4.3. Macro mediator có thể nội sinh

Oil, DXY, VIX và US10Y không phải các biến trung gian hoàn toàn ngoại sinh.

Ví dụ:

- GPR làm VIX tăng;
- giá cổ phiếu giảm cũng làm VIX tăng;
- DXY và equity phản ứng đồng thời trước cùng một tin;
- Oil phản ứng cả với supply risk lẫn kỳ vọng nhu cầu;
- lãi suất Mỹ phản ứng với cả inflation expectation và flight-to-safety.

Do đó, hồi quy thường:

\[
r_{t+h}
=
\theta_{oil}\Delta Oil_t
+
\theta_{vix}VIX_t
+\cdots
\]

chưa thể được diễn giải ngay là tác động nhân quả.

## Hai mode nên được tách rõ

### Reduced-form / explanatory mode

```text
GPR → macro
GPR + macro → market
```

Kết quả chỉ được gọi là:

- transmission attribution;
- explanatory decomposition;
- conditional association.

### Structural / causal mode

Dùng một trong các cách:

- LP-IV;
- proxy-SVAR;
- high-frequency identification;
- narrative shock;
- event identification;
- recursive structural assumptions.

---

# 4.4. GPR level không phải geopolitical shock

Biến:

\[
\ln(1+GPR_t)
\]

chỉ là transformed level, không phải innovation hoặc shock.

Một mức GPR cao có thể bao gồm:

- tin mới;
- tin lặp lại;
- phần đã được dự báo;
- regime kéo dài;
- attention cao nhưng không có event mới.

Cần tách tối thiểu:

\[
Level_t = \ln(1+GPR_t)
\]

\[
Persistent_t = \mathbb{E}_{t-1}[Level_t]
\]

\[
Innovation_t = Level_t - Persistent_t
\]

\[
Jump_t = \max(0, z_t-q_{0.95})
\]

Với GPA:

\[
SurpriseAct_t
=
GPA_t
-
\mathbb{E}_{t-1}
\left[
GPA_t
\mid
GPT_{t-1:t-k},
S\text{-}GPR_{t-1:t-k},
Ladder_{t-1}
\right]
\]

## Khuyến nghị

Đưa decomposition này vào G2.0, không để tới G6.

Các biến cần chạy song song:

```text
GPR_LEVEL
GPR_PERSISTENT
GPR_INNOVATION
GPR_JUMP
GPT_INNOVATION
GPA_SURPRISE
```

---

# 4.5. Variance decomposition hiện có thể sai

Công thức kiểu:

\[
Share_M
=
\frac{\theta_M^2Var(M)}
{Var(r)}
\]

không xử lý:

- covariance giữa Oil, DXY, VIX, US10Y;
- covariance giữa mediator và direct shock;
- tương tác giữa các channel;
- residual variance.

Kết quả có thể dẫn tới:

\[
\sum_M Share_M > 100\%
\]

## Thay thế

### Cho reduced-form model

- Shapley decomposition của \(R^2\);
- LMG decomposition;
- dominance analysis;
- permutation-based contribution;
- rolling historical contribution.

### Cho structural VAR

- FEVD;
- generalized FEVD;
- historical decomposition.

Với sản phẩm giải thích thị trường hàng ngày, historical contribution hữu ích hơn:

```text
VN-Index giảm hôm nay:
- VIX channel: x%
- DXY channel: y%
- Oil channel: z%
- Vietnam-specific shock: k%
- unexplained: phần còn lại
```

---

# 4.6. Gate G2a đang tạo confirmation bias

Gate hiện có xu hướng yêu cầu:

- GPR phải đẩy Oil tăng;
- GPR phải đẩy VIX tăng;
- kết quả phải “đúng literature”.

Điều này nguy hiểm vì không phải geopolitical shock nào cũng có cùng dấu.

Ví dụ:

- trade conflict có thể làm Oil giảm vì nhu cầu kỳ vọng yếu;
- supply disruption có thể làm Oil tăng;
- military threat đã price-in có thể không làm thị trường biến động;
- de-escalation có thể làm VIX giảm;
- shock tài chính có thể làm yield giảm do flight-to-safety.

## Gate nên đổi thành

G2a pass khi:

1. Dữ liệu và pipeline đúng.
2. IRF ổn định qua các specification hợp lý.
3. Confidence interval được báo đầy đủ.
4. Dấu và độ lớn có giải thích kinh tế.
5. Kết quả âm hoặc không có ý nghĩa vẫn được lưu.
6. Specialized channel shock giải thích tốt hơn generic GPR khi phù hợp.

Không dùng “đúng dấu kỳ vọng” làm điều kiện pass.

---

# 4.7. Tần suất dữ liệu chưa đồng nhất

Hệ thống đang kết hợp:

- GPR global daily;
- country GPR monthly;
- VN-Index daily;
- macro monthly/quarterly;
- GDELT monthly;
- statement data có thể intraday.

Không nên forward-fill monthly GPR sang daily vì có thể tạo:

- artificial persistence;
- lead-lag giả;
- standard error sai;
- look-ahead bias;
- repeated synthetic observations.

## Nên tách ba pipeline

| Pipeline | Tần suất | Outcome |
|---|---:|---|
| Daily financial | Daily | return, volatility, FX, alerts |
| Monthly macro | Monthly/quarterly | CPI, IIP, export, FII, GDP |
| Event/intraday | phút/giờ | speaker weight, event study |

### Quy tắc

- GPRC_VNM monthly chỉ dùng cho monthly macro hoặc validation.
- Daily country-specific shock phải lấy từ daily AI-GPR, bilateral index hoặc corpus báo Việt Nam.
- GDELT cần daily aggregate nếu dùng cho alert/backtest.

---

# 4.8. Backtest hiện có nguy cơ biến OOS thành IS

Nếu cùng cửa sổ 2023–2026 được dùng để:

- chọn feature;
- chọn chân B/C;
- sửa rubric;
- chọn model;
- chọn strategy;
- quyết định giữ/bỏ tín hiệu;

thì cửa sổ này không còn là out-of-sample thật sự.

## Đề xuất chia dữ liệu

```text
2015–2020  Development / training
2021–2023  Validation / model selection
2024–2025  Pseudo-OOS walk-forward
2026       Final untouched holdout
```

Có thể khóa:

```text
2026-01-01 → 2026-06-30
```

làm final holdout, nhưng sau khi khóa không được sửa model dựa trên kết quả của giai đoạn này.

## Bổ sung kiểm định

- Hansen SPA;
- White Reality Check;
- Deflated Sharpe Ratio;
- block bootstrap;
- multiple-testing correction;
- purging và embargo;
- confidence interval cho IC;
- confidence interval cho chênh lệch Sharpe;
- transaction cost sensitivity.

Không nên chỉ dùng gate:

```text
IC > 0.03
Sharpe > benchmark
```

Mà cần:

```text
incremental IC > 0
với confidence interval đủ rõ
và ổn định qua regime
và còn hiệu quả sau phí
```

---

# 4.9. LLM validation chưa đủ nếu chỉ dùng correlation

Correlation với human hoặc GPT cao chưa đảm bảo model tốt.

Một model vẫn có thể:

- bỏ sót ACT hiếm;
- đánh thấp toàn bộ score;
- sai ở quoted speech;
- sai actor/target;
- đúng với bài dễ nhưng sai trong crisis;
- có correlation cao vì phần lớn bài đều bằng 0.

## Bộ metric đề xuất

### Score liên tục

- Pearson;
- Spearman;
- MAE;
- RMSE;
- calibration curve;
- score-bucket bias;
- intraclass correlation.

### Nhãn

- precision;
- recall;
- macro-F1;
- class-specific F1;
- weighted Cohen’s kappa;
- confusion matrix;
- false-negative rate cho ACT;
- false-positive rate cho historical/quoted/metaphorical cases.

### Extraction

- actor exact match;
- target exact match;
- directed pair accuracy;
- channel macro-F1;
- speaker-role accuracy;
- origin accuracy.

### Robustness

- prompt paraphrase;
- model-version stability;
- source holdout;
- temporal holdout;
- crisis vs non-crisis;
- Vietnamese original vs translated;
- long article vs short article.

Qwen chỉ được thay GPT khi đạt yêu cầu trên **human gold set**, không chỉ tương quan với GPT.

---

# 4.10. Severity và Threat/Act đang bị trộn

Thiết kế hiện tại gần với:

```text
0.4–0.6 = THREAT
0.7–1.0 = ACT
```

Điều này trộn hai chiều khác nhau:

- mức độ nghiêm trọng;
- trạng thái đã xảy ra hay chưa.

Một act nhẹ có thể severity thấp.  
Một nuclear threat có thể severity rất cao.

## Schema đề xuất

```json
{
  "relevance": 0.0,
  "severity": 0.0,
  "threat_score": 0.0,
  "act_score": 0.0,
  "escalation_direction": 0.0,
  "confidence": 0.0,
  "actor": null,
  "target": null,
  "channel": null,
  "origin": null
}
```

Cho phép:

```text
ACT severity thấp
THREAT severity cao
Bài có cả threat và act
```

Không ép một bài chỉ có đúng một nhãn.

---

# 4.11. Denominator và coverage báo chí cần kiểm soát

Công thức:

\[
GPR_t
=
100
\frac{\sum_i s_i}{N_t}
\]

hợp lý, nhưng corpus báo Việt Nam có thể bị ảnh hưởng bởi:

- thiếu archive;
- crawler lỗi;
- thay đổi số lượng nguồn;
- thay đổi chính sách biên tập;
- một nguồn đăng nhiều hơn các nguồn khác;
- cùng một tin được đăng lại nhiều lần.

## Balanced source index

Tính riêng từng nguồn:

\[
GPR_{s,t}
=
\frac{\sum_{i \in (s,t)}score_i}
{N_{s,t}}
\]

Sau đó tổng hợp:

\[
GPR_t
=
\sum_s w_s GPR_{s,t}
\]

Trong đó \(w_s\) được cố định theo version.

## Cần lưu quality metadata

```text
source_coverage_count
expected_article_count
crawl_completeness
duplicate_cluster_count
effective_article_count
missing_source_flag
index_quality_flag
```

Ngày không đủ coverage phải bị gắn cờ, không được im lặng tính index như bình thường.

---

# 4.12. Dedup cần theo event cluster

URL và SimHash chỉ bắt được duplicate gần giống. Tin Reuters/AP/AFP được viết lại hoặc dịch có thể không bị bắt.

Cần tách:

## Media Attention Index

Cho phép nhiều bài cùng nói về một sự kiện:

\[
Attention_t
=
\frac{\sum_i score_i}{N_t}
\]

## Event Risk Index

Mỗi event cluster chỉ được tính một lần:

\[
EventRisk_t
=
\sum_{e \in E_t}
severity_e
\times
novelty_e
\times
confidence_e
\]

Trong một cluster:

```text
first_seen_at
article_count
source_count
media_amplification
event_severity
event_novelty
event_persistence
```

Điều này giúp chân A đo attention, còn chân C đo event thực tế.

---

# 4.13. S-GPR có selection bias và official silence

Nguồn phát ngôn chính thức không phải random sample.

Có thể xảy ra:

- chính phủ im lặng trong crisis;
- một cơ quan đăng rất nhiều nội dung thủ tục;
- dữ liệu thay đổi theo nhiệm kỳ;
- nguồn tiếng Anh không phản ánh đầy đủ bản gốc;
- số lượng phát ngôn biến động mạnh theo thời gian.

Không nên chỉ dùng một chỉ số normalized mean.

## Nên giữ ba biến

\[
S\text{-}GPR^{sum}_t = \sum_i score_i
\]

\[
S\text{-}GPR^{mean}_t
=
\frac{\sum_i score_i}{N_t}
\]

\[
S\text{-}GPR^{max}_t
=
\max_i score_i
\]

Cần thêm:

```text
official_silence_days
expected_source_activity
statement_volume
missing_source_flag
source_regime
```

“Không phát ngôn” đôi khi là thông tin, không chỉ là missing data.

---

# 4.14. Actor weighting có endogeneity

Hệ số phản ứng thị trường quanh phát ngôn của một speaker không tự động đo “độ uy tín” của speaker.

Lãnh đạo cấp cao thường phát biểu đúng lúc sự kiện lớn xảy ra. Hệ số lớn có thể đến từ:

- severity lớn;
- thời điểm đặc biệt;
- market volatility cao;
- event lớn hơn;
- attention lớn hơn;
- selection của speaker.

## Cần kiểm soát

```text
severity
channel
specificity
act/threat
country pair
event fixed effect
time fixed effect
pre-event volatility
market-wide news
attention
```

Ở V1, nên gọi đây là:

> **predictive actor weight**

Không claim causal influence.

---

# 4.15. GDELT monthly không đủ cho daily warning

Nếu GDELT chỉ được aggregate monthly, nó phù hợp với:

- macro;
- panel;
- long-run relationship.

Nó không phù hợp với:

- daily alert;
- lead-lag vài ngày;
- daily backtest;
- escalation warning.

## Nên có hai bảng

```text
gdelt_pair_daily
gdelt_pair_monthly
```

Daily aggregate chỉ cần cho các country pair trọng điểm, không cần tải toàn bộ raw event.

---

# 4.16. LLM historical reconstruction pre-1979 là phần rủi ro cao

LLM tự liệt kê sự kiện lịch sử có thể tạo ra:

- availability bias;
- hindsight bias;
- mật độ sự kiện không đồng nhất;
- sai ngày;
- bỏ sót event nhỏ;
- nhớ nhiều event nổi tiếng hơn event ít nổi;
- chuỗi nhìn hợp lý nhưng không có sampling frame.

## Khuyến nghị

- Không dùng pre-1979 LLM reconstruction trong main causal model.
- Chỉ dùng cho exploratory appendix hoặc narrative database.
- Mỗi event phải có ít nhất:
  - event date;
  - publication date;
  - retrieval source;
  - verification status;
  - source count;
  - confidence;
  - version.
- Không để model web-search tự do.
- Phải search trong một tập archive hoặc nguồn xác định trước.

---

# 5. KIẾN TRÚC CÔNG THỨC ĐỀ XUẤT

# 5.1. Tầng 0 — Chấm điểm nội dung

Cho mỗi article/statement/event \(i\):

\[
x_i
=
(
relevance_i,
severity_i,
threat_i,
act_i,
direction_i,
confidence_i
)
\]

Metadata:

```text
actor
target
channel
origin
speaker
speaker_role
commitment
specificity
event_cluster_id
source
published_at
available_at
model_version
rubric_version
```

---

# 5.2. Tầng 1 — Xây chỉ số

## Attention index

\[
Attention_t
=
100
\times
\frac{1}{N_t}
\sum_{i \in D_t}
relevance_i
\times
severity_i
\]

## Threat index

\[
GPT_t
=
100
\times
\frac{1}{N_t}
\sum_i threat_i
\]

## Act index

\[
GPA_t
=
100
\times
\frac{1}{N_t}
\sum_i act_i
\]

## Event risk

\[
EventRisk_t
=
\sum_{e \in E_t}
severity_e
\times
novelty_e
\times
confidence_e
\]

## Bilateral index

\[
BIGPR^{a\rightarrow b}_t
=
100
\times
\frac{1}{N_t}
\sum_i
score_i
\cdot
\mathbb{1}
(actor_i=a,target_i=b)
\]

---

# 5.3. Tầng 1.5 — Decomposition thành shock

\[
Level_t = \ln(1+GPR_t)
\]

\[
Persistent_t
=
\widehat{\mathbb{E}}_{t-1}[Level_t]
\]

\[
Innovation_t
=
Level_t-Persistent_t
\]

\[
SurpriseAct_t
=
GPA_t
-
\widehat{\mathbb{E}}_{t-1}
[GPA_t]
\]

Expectation phải được fit rolling và chỉ dùng dữ liệu có sẵn tại thời điểm \(t-1\).

---

# 5.4. Tầng 2 — Global Macro Response

Với từng mediator:

\[
M
\in
\{
\Delta \ln Oil,
\Delta \ln DXY,
VIX,
\Delta US10Y,
EMSpread
\}
\]

Local Projection:

\[
M_{t+h}
=
a^{(h)}_M
+
\sum_j
\gamma^{(h)}_{M,j}
Shock^j_t
+
\sum_{k=1}^{p}
\rho^{(h)}_{M,k}M_{t-k}
+
\Gamma^{(h)}Z_t
+
u_{M,t+h}
\]

Shock có thể là:

```text
GPR innovation
GPT innovation
GPA surprise
Energy GPR shock
Trade GPR shock
Sanction GPR shock
Military GPR shock
```

Output:

```text
IRF_M,j(h)
confidence interval
specification stability
regime split
```

---

# 5.5. Tầng 3 — Country Transmission

\[
\begin{aligned}
r^c_{t+h}
=
\alpha^c_h
&+
\sum_j
\beta^c_{j,h}Shock^j_t \\
&+
\sum_M
\theta^c_{M,h}M_t \\
&+
\lambda^c_h GPR^{c,\perp}_t \\
&+
\Phi^c_h X^c_t
+
\varepsilon^c_{t+h}
\end{aligned}
\]

Trong đó:

- \(\beta\): global-direct;
- \(\theta\): macro channel sensitivity;
- \(\lambda\): domestic-direct;
- \(X^c\): controls nội địa.

---

# 5.6. Dynamic indirect effect

\[
\boxed{
Indirect_{j\rightarrow c}(h)
=
\sum_M
\sum_{s=0}^{h}
\gamma_{M,j}(s)
\theta^c_M(h-s)
}
\]

Tổng global effect:

\[
Total^{global}_{j\rightarrow c}(h)
=
Direct^{global}_{j\rightarrow c}(h)
+
Indirect_{j\rightarrow c}(h)
\]

Domestic effect:

\[
Total^{domestic}_{c}(h)
=
\lambda^c_h
\]

Ở reduced-form version, đây là decomposition, chưa phải causal mediation.

---

# 6. BUILD ORDER ĐỀ XUẤT

# G0 — Research Governance

Làm trước ingest.

## Deliverables

- hypothesis registry;
- data dictionary;
- available-time policy;
- final holdout policy;
- multiple-testing policy;
- causal claims matrix;
- model/prompt/data versioning policy;
- publication/revision policy.

## Causal claims matrix mẫu

| Thành phần | Claim cho phép |
|---|---|
| LLM score | measurement |
| GPR → return OLS/LP | association / predictive |
| GPR innovation → market LP | reduced-form response |
| LP-IV / proxy-SVAR | structural response nếu instrument hợp lệ |
| two-stage coefficient product | transmission decomposition |
| dynamic mediation có identification | causal mediation |

---

# G1 — Ingest & Data Audit

Giữ các phần hiện có, bổ sung:

```text
date
published_at
available_at
loaded_at
revised_at
source_version
data_version
quality_flag
```

## Quy tắc quan trọng

Backtest chỉ được dùng dữ liệu khi:

\[
available\_at \le decision\_time
\]

Không dùng `date` như proxy cho thời điểm dữ liệu thực sự được biết.

---

# G2 — Reduced-form Baseline

## G2.0

- load data;
- align frequency;
- build level/persistent/innovation/surprise;
- audit publication time;
- create daily/monthly/event datasets.

## G2a

```text
GPR innovation → Global Macro
```

Chạy LP cho:

- Oil;
- DXY;
- VIX;
- US10Y;
- EM spread.

## G2b

```text
GPR innovation → VN market
```

Chạy direct reduced-form trước, chưa mediation.

## G2c

So sánh:

```text
generic GPR
vs
channel-specific GPR
vs
threat
vs
act surprise
```

---

# G2.5 — Structural Identification

Ưu tiên ba channel:

1. Oil supply disruption.
2. Trade/tariff shock.
3. Global risk-off shock.

Phương pháp:

- proxy-SVAR;
- LP-IV;
- event identification;
- high-frequency surprise;
- narrative restrictions.

---

# G3 — Locked Backtest

## Benchmark tối thiểu

```text
buy-and-hold
VIX-only
DXY-only
Oil-only
momentum
volatility
non-GPR combined model
```

Câu hỏi chính:

> GPR có tạo incremental predictive value sau khi đã biết VIX, DXY, Oil, momentum và volatility hay không?

## Metrics

- IC 5/20/60 ngày;
- Sharpe;
- MaxDD;
- turnover;
- hit rate;
- drawdown duration;
- cost-adjusted return;
- Deflated Sharpe;
- confidence interval.

---

# G4 — Serving Risk Monitor

Có thể triển khai ngay cả khi alpha fail.

Các output phù hợp:

```text
geopolitical risk level
geopolitical innovation
threat/act split
channel attribution
global macro regime
country exposure
historical analog
confidence
quality flag
```

---

# G5 — S-GPR

Chỉ bắt đầu khi:

- source coverage ổn;
- timestamp đủ tốt;
- statement normalization pass;
- silence/missingness được mô hình hóa.

---

# G6 — Physical Events

- GDELT daily cho financial track;
- GDELT monthly cho macro track;
- LLM reconstruction chỉ dùng exploratory;
- event cluster và first-seen timestamp bắt buộc.

---

# G7 — Fusion

So sánh nested:

```text
A
A+B
A+C
A+B+C
A+B+C+divergence
```

Mỗi bước phải báo:

- delta IC;
- delta Sharpe;
- delta forecast loss;
- confidence interval;
- regime stability;
- complexity penalty;
- data cost;
- operational cost.

---

# 7. SCHEMA DỮ LIỆU BỔ SUNG

# 7.1. `ext_series`

```sql
CREATE TABLE ext_series (
    series_id TEXT NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE PRECISION,
    available_at TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL,
    revised_at TIMESTAMPTZ,
    source_version TEXT,
    data_version TEXT NOT NULL,
    quality_flag TEXT,
    PRIMARY KEY (series_id, observation_date, data_version)
);
```

# 7.2. `article_scores`

```sql
CREATE TABLE article_scores (
    article_id BIGINT NOT NULL,
    relevance DOUBLE PRECISION,
    severity DOUBLE PRECISION,
    threat_score DOUBLE PRECISION,
    act_score DOUBLE PRECISION,
    escalation_direction DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    actor TEXT,
    target TEXT,
    channel TEXT,
    origin TEXT,
    speaker_name TEXT,
    speaker_role TEXT,
    commitment TEXT,
    specificity DOUBLE PRECISION,
    event_cluster_id TEXT,
    model_version TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    scored_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (article_id, model_version, rubric_version)
);
```

# 7.3. `index_quality`

```sql
CREATE TABLE index_quality (
    index_name TEXT NOT NULL,
    date DATE NOT NULL,
    source_coverage_count INTEGER,
    expected_article_count INTEGER,
    crawl_completeness DOUBLE PRECISION,
    duplicate_cluster_count INTEGER,
    effective_article_count INTEGER,
    missing_source_flag BOOLEAN,
    quality_flag TEXT,
    data_version TEXT NOT NULL,
    PRIMARY KEY (index_name, date, data_version)
);
```

---

# 8. CHECKLIST TRƯỚC KHI CODE G2

## Bắt buộc

- [ ] Tách global-direct và domestic-direct.
- [ ] Sửa mediation thành dynamic convolution.
- [ ] Đổi tên causal mediation thành transmission decomposition ở V1.
- [ ] Thêm GPR innovation/persistent/surprise.
- [ ] Thêm `available_at`.
- [ ] Tách daily/monthly/intraday pipeline.
- [ ] Không forward-fill country monthly GPR vào daily model.
- [ ] Khóa final holdout.
- [ ] Thêm multiple-testing policy.
- [ ] Thay variance-share đơn giản bằng Shapley/FEVD.
- [ ] Tách severity khỏi threat/act.
- [ ] Xây human gold set cho LLM validation.
- [ ] Thêm event clustering.
- [ ] Thêm coverage quality flag.
- [ ] Bỏ điều kiện “IRF phải đúng dấu literature”.

## Nên làm

- [ ] Thêm EM spread vào global macro mediators.
- [ ] Tách risk-off shock khỏi geopolitical supply shock.
- [ ] Xây baseline không dùng GPR.
- [ ] Lưu toàn bộ failed runs.
- [ ] Version hóa prompt, model, data và report.
- [ ] Tạo causal claims matrix.
- [ ] Thêm historical contribution cho serving.

---

# 9. KẾT LUẬN

Hệ thống hiện tại có ba ưu điểm lớn:

1. Kiến trúc nghiên cứu có logic.
2. Có khả năng tạo sản phẩm độc lập ngay cả khi alpha không đạt.
3. Có tiềm năng đóng góp mới qua divergence giữa attention, intent và acts.

Rủi ro lớn nhất không nằm ở code hoặc hạ tầng, mà nằm ở:

- định nghĩa shock;
- nhận dạng nhân quả;
- dynamic transmission;
- leakage trong backtest;
- validation LLM;
- tần suất dữ liệu;
- duplicate và coverage bias.

Sau khi sửa các điểm trên, hệ thống sẽ có hai đường giá trị rõ ràng:

```text
Đường 1: Research / Macro Risk
GPR shock → macro channel → country impact

Đường 2: Investment Product
risk regime → exposure adjustment → portfolio / alert
```

Ngay cả khi không tạo được alpha giao dịch ổn định, engine vẫn có giá trị cao cho:

- risk monitoring;
- scenario analysis;
- market explanation;
- portfolio stress testing;
- early warning;
- country exposure mapping.

Điều kiện quan trọng là phải phân biệt rõ:

```text
measurement
association
prediction
structural response
causal effect
```

và chỉ đưa ra claim tương ứng với mức độ nhận dạng mà mô hình thực sự đạt được.
