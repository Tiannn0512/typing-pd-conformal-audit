# 查新扫描 W4（2026-09-26）

**执行**：TODO-3.6，W4 月度扫描①（基线 = 02_查新报告/查新报告_打字动力学x帕金森x共形预测.md，2026-09-25）
**工具**：WebSearch（7 组查询）+ WebFetch 直读 arXiv API / Europe PMC API / Semantic Scholar API
**扫描窗口**：近 4 个月（2026-05-26 起）优先

---

## 一、查询记录

### Q1 "keystroke dynamics conformal prediction"（WebSearch）
- 命中：无直接组合。arXiv API 直查 `all:"keystroke" AND all:"conformal"` = **0 条**。
- 前 3 条：
  1. Quantifying DL Model Uncertainty in Conformal Prediction — Karimi & Samavi, AAAI-HUMAN 2023（该组有击键认证背景， Toronto Met，见建议）— https://www.ee.torontomu.ca/~samavi/pubs.html
  2. Conformal Prediction for Offensive Security — arXiv:2609.05165（无关）— https://arxiv.org/abs/2609.05165
  3. Keystroke Dynamics survey — arXiv:2303.04605（无 CP）— https://arxiv.org/abs/2303.04605

### Q2 "typing + Parkinson + conformal prediction / uncertainty quantification"（WebSearch + Europe PMC API）
- Europe PMC `"typing" AND "Parkinson" AND "conformal prediction"` = 2 条，均为会议摘要书噪声。
- 前 3 条：
  1. Diaz-Rincon et al., Uncertainty-Aware Prediction of PD Medication Needs（MLHC 2025 / PMLR v298）— 已在基线 — https://arxiv.org/abs/2508.10284
  2. **CASCADE Conformal Prediction（2026 新作，同组）** — 见 Q9 — https://www.themoonlight.io（摘要聚合）
  3. Azad et al. 2025, Beyond Accuracy: UQ in PD Diagnosis — PMC12718125（非打字模态）— https://pmc.ncbi.nlm.nih.gov/articles/PMC12718125

### Q3 "keystroke dynamics + Parkinson + 2026 dataset"（WebSearch）
- 命中：3 条新文献，均无 CP/UQ：
  1. **IRL for Interpretable Keystroke Biomarkers in PD — arXiv:2606.25270（2026-06，新）**，MIT-CSXPD — https://arxiv.org/abs/2606.25270
  2. **Backspace as a Natural Experiment（AFT 模型）— arXiv:2607.24796（2026-06-30 提交，v2 2026-08-31，新）**，MIT-CSXPD n=57 — https://arxiv.org/abs/2607.24796
  3. Gentiyal et al. 2026, PD Detection Using Keystroke Dynamics（DL 框架，JETIA）— https://itegam-jetia.org

### Q4 四库数据集专项（"MIT-CSXPD / Tappy / TyPD"，WebSearch + arXiv API）
- arXiv API `abs:"Parkinson" AND abs:"keystroke"` 全库仅 **2 篇**（2607.24796、2510.15950），均无 CP。
- TyPD 库（Mendeley 2023, 500+ 受试者）2026 窗口内无新使用论文；Online English 库无新命中。
- 附带命中：Tat et al. 2025 磁弹性智能键盘（硬件模态，被引 26）— https://pmc.ncbi.nlm.nih.gov（非算法/非 UQ）。

### Q5 SGC-RML 团队（arXiv:2605.08302）后续
- 确认原文：Wei W. et al., 2026-05-08，"SGC-RML: reliable and interpretable longitudinal…"，模态 = 语音/步态/可穿戴/行动任务/临床变量 → 8 维症状节点空间。
- **无打字模态；窗口内无该组后续论文扩展到打字。** 判定不变。

### Q6 Francesconi / Sicilia / Guarrasi 组（arXiv:2510.15950）后续
- arXiv API `au:"Guarrasi"` 共 51 篇（读取前 25）：**无任何 2510.15950 的 UQ/CP 后续**。
- Semantic Scholar 引文（2510.15950）= **仅 2 条**：arXiv:2606.25270（IRL，无 UQ）+ "Next-gen health" 综述（2025）。
- 该组新动向：arXiv:2602.18535（2026-02）Fairness-Aware Partial-label Domain Adaptation for **PD/ALS 语音**分类——跨域 PD 兴趣转向语音模态，仍无 UQ — https://arxiv.org/abs/2602.18535

### Q7 Diaz-Rincon 组后续
- **确认新作：CASCADE Conformal Prediction: Uncertainty-Adaptive Prediction Intervals for Two-Stage Clinical Decision Support（2026，Diaz-Rincon, Liang, Ramirez-Zamora, Shickel 等）**——PD 用药管理两阶段 CP 区间。
- 模态仍为临床变量/用药，**不含打字**。

### Q8 方法学竞品引用动态（Audited CP）
- arXiv:2606.14909 = Zhou, Fathony, Nguyen, Sesia, "Audited Conformal Prediction for Classification under Unknown Distribution Shift"（2026-06）。
- arXiv:2607.18088 = Weijia Han 等, "The Label Complexity of Class-Conditional Coverage under Distribution Shift"（2026-07）— https://arxiv.org/abs/2607.18088
- 引用动态：2606.14909 被 "Does Marginal Coverage Guarantee Class-Conditional Safety?"（2026-08，方法学）引用；**无任何击键/PD 应用端引用**。

### Q9 泛查（"conformal coverage audit / cross-dataset coverage"、PD digital biomarker × CP）
- Ring 可穿戴 + CP 90% 覆盖（2026-06，ResearchGate，健康监测非 PD 非打字）。
- EMBC 2026 收录 CP 睡眠呼吸筛查等（非 PD 非打字）。
- 2026 PD 数字生物标记综述（PMC13135170）确认"PD 数字表型 × CP"仍无系统工作。
- Europe PMC `"keystroke" AND "conformal"` = 16 条，**全部为放疗"conformal"噪声**，零真命中。

---

## 二、判定：**黄色（邻区推进），无红色精确命中**

### 红色警报检查：精确空位仍为空
打字/击键 × PD × 共形覆盖审计 = **0 篇**。三路独立验证：arXiv API（0 条）、Europe PMC（16 条全噪声）、arXiv 全库 abs 检索仅 2 篇击键-PD 论文且均无 CP。预注册 v1.0-prereg 的精确空位安全。

### 黄色项（逐条）
| # | 项 | 理由 |
|---|---|---|
| Y1 | arXiv:2606.25270 IRL 击键 PD（2026-06） | 同库（MIT-CSXPD）新判别论文，引用了 Francesconi 四库工作；无 UQ/CP。说明该库竞争在加速 |
| Y2 | arXiv:2607.24796 Backspace AFT（2026-06-30 / v2 08-31） | 同库新分析论文（n=57），仅 bootstrap CI；无 CP。击键-PD 的"公共数据集挖掘"持续升温 |
| Y3 | Gentiyal 2026（JETIA） | 又一篇 DL 击键-PD 检测，无 UQ |
| Y4 | Diaz-Rincon 组 CASCADE（2026） | "PD × CP"团队在临床决策支持方向续作成功——证明该组有能力也有意愿持续做 CP×PD，模态外扩（如打字）风险实在 |
| Y5 | Guarrasi 组转语音跨域（arXiv:2602.18535） | 四库管线作者组的跨域 PD 方法积累转向语音，短期补 UQ/覆盖概率下降，但组内方法可迁移 |

### 绿色项
SGC-RML（无打字扩展）；2606.14909 / 2607.18088（纯方法学，无应用端触及本域）；EMBC 2026 CP 应用（睡眠/可穿戴）；Tat 2025 硬件键盘；放疗"conformal"噪声；Azad 2025 UQ-PD（非打字）。

---

## 三、与 2026-09-25 基线的增量

**新出现（基线未收录）：**
1. arXiv:2606.25270 — IRL 可解释击键生物标记（MIT-CSXPD，2026-06）
2. arXiv:2607.24796 — Backspace 自然实验 / AFT 模型（MIT-CSXPD，2026-06-30，v2 2026-08-31）
3. Gentiyal et al. 2026 — DL 击键-PD 检测（JETIA）
4. **CASCADE Conformal Prediction** — Diaz-Rincon 组 2026 续作（CP×PD 用药两阶段）
5. arXiv:2602.18535 — Guarrasi 组 PD/ALS 语音公平性跨域 DA（2026-02）

**状态更新：**
- SGC-RML：确认模态清单不含打字；窗口内无后续 → 威胁等级不变（中）。
- Francesconi 2510.15950：引文仅 +2（IRL、综述），**无人补 UQ/覆盖** → 空位维持。
- Audited CP（2606.14909）/2607.18088：引用仍在方法学内部循环，无领域应用 → 竞品威胁不变（低）。

---

## 四、建议动作

**总判定：黄色 → 继续执行，无抢发，预注册冻结（v1.0-prereg）不受影响。**

1. **继续推进**：精确空位（打字×PD×共形覆盖审计，四库）经三路独立验证仍为空。基线"窗口 ≤12 个月"估计维持且趋紧（4 个月内同库新论文 +3）。
2. **差异化要点（写入 related work / discussion）**：
   - 2606.25270、2607.24796、Gentiyal 2026 均为"判别力裸奔"（无 UQ/覆盖保证）——作为"邻区活跃但覆盖审计缺位"的直接证据引用；
   - 相对 Audited CP（2606.14909）：我们将其审计范式首次落到医学模态应用端（其引用图尚未触及击键/PD）；
   - 相对 CASCADE：明确模态边界（临床变量/用药 vs 打字行为），引言中预防性划界。
3. **监视名单扩充**：Bondade（backspace 组）；2606.25270 作者；Gentiyal；Diaz-Rincon/UF 团队（CASCADE 后续）；Guarrasi 组；**新增 Toronto Met Samavi/Karimi 组**（同时具备击键认证与 conformal 方法双重背景的潜在进入者）。
4. **W8（下次月度）扫描新增查询**："CASCADE conformal typing"；Semantic Scholar 引文监控 2606.14909 / 2607.18088 / 2510.15950；arXiv API `abs:"keystroke" AND abs:"uncertainty"`。

---

*扫描完成时间：2026-09-26。全部 18 项查询/直读记录如上，可复现。*
