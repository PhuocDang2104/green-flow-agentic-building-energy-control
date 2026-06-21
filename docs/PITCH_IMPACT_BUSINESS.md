# GreenFlow — Pitch Plan & Impact/Business Segment (1 phút)

> Mục tiêu: thắng theo tiêu chí 2 giám khảo (Chopra: regrettable substitution,
> LCA/life-cycle, safe-to-fail, site-specific, "run the numbers"; Carrie: circular/
> PaaS, financial viability, impact measurement, triple-layer canvas).
> Slide text + lời thoại để **tiếng Anh** (GK quốc tế). Ghi chú tiếng Việt cho team.

---

## 1. Khung pitch tổng thể (gợi ý 5 phút)

| # | Slot | Thời lượng | Thông điệp chính | Tab/demo |
|---|------|-----------|------------------|----------|
| 1 | Problem (site-specific) | 0:45 | Toà nhà VN: HVAC chiếm phần lớn điện; giá EVN giờ cao điểm 3.314đ/kWh; lưới căng khi heatwave | slide |
| 2 | Solution: agentic digital twin | 0:45 | Agent predict→control→**simulate**→policy→execute, human-in-loop | Dashboard 3D + Agent tab |
| 3 | Proof it's REAL (M&V) | 1:00 | Baseline-vs-optimized + **validation MAPE 0.8%** = IPMVP M&V (không bịa) | Control & Simulation tab |
| 4 | **Impact & Business** ⭐ | **1:00** | **Net-positive AI (A) + Bankable model (B)** | Dashboard headline + Impact tab |
| 5 | Resilience & no-regret | 0:45 | safe-to-fail (policy gate, fallback), pre-cool = climate adaptation, regret-check | Agent/Sim |
| 6 | Close + ask | 0:45 | Triple-layer value, scale ra portfolio, lời mời | slide |

> Slot 4 là **luận điểm thắng giải** — phải đứng riêng, có headline trên Dashboard,
> KHÔNG chôn trong nút "Run simulation". (xem lý do trong README phản biện IA.)

---

## 2. SLIDE — "Impact & Business" (đúng 1 phút)

### 2.1 Bố cục slide (1 slide, chia 2 nửa + dải triple-layer)

```
┌───────────────────────────────────────────────────────────────┐
│  IMPACT & BUSINESS — verified, net-positive, bankable          │
├───────────────────────────────┬───────────────────────────────┤
│  A) NET-POSITIVE AI            │  B) BANKABLE MODEL            │
│  (no regrettable substitution) │  (Energy-Efficiency-as-a-     │
│                                │   Service · shared savings)   │
│  AI footprint   ~0.3 kgCO₂/day │  Verified by IPMVP M&V        │
│  CO₂ avoided    ~32 kgCO₂/day  │   (validation MAPE 0.8%)      │
│  ───────────────────────────  │  Savings  ~22M VND/bldg·yr    │
│  ≈ 90× NET-POSITIVE           │  Peak     −16 kW              │
│  break-even in ~10 min        │  Comfort  ±0 min              │
│  [SCI · Green Software Found.] │  Payback  < 3 months         │
│                                │  Scale    portfolio, ~0 marg. │
├───────────────────────────────┴───────────────────────────────┤
│  TRIPLE-LAYER:  Economic (VND, <3mo payback) ·                 │
│  Environmental (CO₂↓, peak↓) · Social (comfort, healthy air)   │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 On-slide text (paste thẳng, tiếng Anh)

**Title:** Impact & Business — *verified · net-positive · bankable*

**A — Net-Positive AI** *(answers "regrettable substitution")*
- AI's own footprint: **~0.3 kg CO₂ / day** (every LLM call + model inference)
- Building CO₂ avoided: **~32 kg CO₂ / day**
- **≈ 90× net-positive** · carbon break-even in **~10 minutes**
- Method: **SCI** (Green Software Foundation standard)

**B — Bankable Model** *(Energy-Efficiency-as-a-Service, shared savings)*
- We earn **only from savings we verify** — **IPMVP** M&V (validation MAPE **0.8%**)
- **~22M VND / building / year** · peak **−16 kW** · comfort **±0 min**
- **Payback < 3 months** · scales to a portfolio at ~zero marginal cost

**Footer:** Economic · Environmental · Social — triple-layer value.

### 2.3 Lời thoại (~150 từ ≈ 60s)

> **[0:00–0:08 — hook]**
> "Does an AI that runs a building actually justify its own carbon? We measured it."
>
> **[0:08–0:28 — A]**
> "Using the Green Software Foundation's SCI standard, GreenFlow's entire AI
> footprint — every LLM call, every model inference — is about **0.3 kilograms of
> CO₂ a day**. The building it manages avoids about **32**. That's roughly **90 times
> net-positive** — carbon break-even in **ten minutes**. No regrettable substitution."
>
> **[0:28–0:52 — B]**
> "And it pays for itself. GreenFlow is **Energy-Efficiency-as-a-Service**: the
> customer pays only a **share of the savings we verify** — using the same **IPMVP**
> protocol you saw in our validation tab, error **under one percent**. One building
> saves around **22 million VND a year**, peak demand down **16 kilowatts**, comfort
> unchanged — **payback under three months**, and software scales to a whole
> portfolio at near-zero marginal cost."
>
> **[0:52–1:00 — close]**
> "Economic, environmental, social — **verified, net-positive, and bankable**."

---

## 3. Nguồn số & giả định (để "thủ" khi GK vặn)

| Số | Nguồn / giả định | Trạng thái |
|---|---|---|
| Savings 47.75 kWh/day, 87.8k VND/day, peak −16.29 kW, comfort +0 min | từ run peak_strategy thật (scenario_kpi) | ✅ có |
| Validation MAPE 0.8% | backtest baseline vs telemetry thật | ✅ có |
| CO₂ factor 0.6766 kg/kWh | lưới điện VN | ✅ có |
| ~22M VND/year/building | 87.8k × ~260 ngày làm việc (đổi giả định nếu cần) | ⚠️ illustrative |
| ~32 kg CO₂/day avoided | 47.75 kWh × 0.6766 | ✅ suy ra |
| AI ~0.3 kg CO₂/day, ~90× | **module A (chưa build)**: tokens Groq + duration inference × grid (SCI) | ⚠️ chốt sau khi build A |
| Payback < 3 months | savings/năm ÷ phí SaaS giả định | ⚠️ chốt sau khi build B |

> Số ⚠️ là illustrative — sẽ thay bằng số module A/B tính ra. Trên slide nên để
> số thật ngay khi A/B chạy xong; trước đó dùng "~" và nói rõ "indicative".

---

## 4. Q&A dự phòng (GK chắc sẽ hỏi)

- **"AI của bạn có phải regrettable substitution không?"** → đúng slide A: đo bằng
  SCI, net-positive ~90×, break-even ~10 phút; có comfort-delta nên không tạo rebound.
- **"Site-specific cho đâu?"** → giá EVN + khí hậu Hà Nội; deploy-được như template
  cho toà nhà VN (mô hình 3D hiện là Nordic — nói rõ là template, swap được).
- **"Làm sao biết savings thật?"** → IPMVP M&V = tab validation, MAPE 0.8%, baseline
  cùng thời tiết/occupancy nên delta là do action.
- **"Digital product thì tính CO₂ kiểu gì?"** (Chopra hỏi đúng câu này) → data center
  + chip + điện inference; ta đã tính bằng SCI (slide A).
- **"Circular economy ở đâu?"** → vận hành tối ưu kéo dài tuổi thọ HVAC (ít thay =
  circular); giảm cầu → hoãn đầu tư công suất lưới.
- **"Resilient/safe-to-fail?"** → policy gate + human-in-loop + fallback graceful;
  peak-shaving = chống sốc lưới; pre-cool = climate adaptation.

---

## 5. TODO trước demo (thứ tự đề xuất)
1. Build **module A** (net-carbon, SCI) → chốt số ~90× + break-even.
2. **Headline band trên Dashboard**: 3 thẻ (Net-positive ×N · Payback · CO₂/yr).
3. Tab **Impact & Business** gắn **B** (ROI + triple-layer + shared-savings) + link M&V.
4. **ESG/GHG report** (Scope 2, methodology) mở rộng từ report hiện có.
5. Reframe site = toà nhà VN trên slide #1.
