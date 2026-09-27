# 查新报告：打字动力学 × 帕金森检测 × 共形预测

**查新日期**：2026-09-25（信号数据线智能体 + 文献核实智能体双通道：arXiv API / Europe PMC / PhysioNet 直读 / 定向网络检索）

---

## 一、竞争判定：精确空位 = 开

- **共形预测 × 打字 × 帕金森：全域零命中**（arXiv 摘要级 + Europe PMC 多轮检索）。
- 领域内最近邻仅两篇，都不构成占位：
  1. **Diaz-Rincon et al. 2025, COPA/PMLR**：PD 患者用药需求的 conformal 区间——用 CP 但非打字数据；
  2. **SGC-RML（arXiv:2605.08302, 2026.05）**：把 conformal calibration + 选择性拒绝用于**多模态** PD 数字评估（语音/步态/可穿戴/mPower）——**不含打字模态**。⚠️ 邻接警报：说明"PD 数字表型 × CP"刚被人开题，打字是最后一块空地之一，窗口估计 ≤12 个月。
- 打字-PD 检测本体：活跃但未饱和（Europe PMC 约 15 篇核心：Giancardo 2016 奠基 → Arroyo-Gallego 2018 居家验证 → Tripathi 2023 IEEE TBME → Sci Adv 2025 → KeyGAN 2025 → Francesconi 2025 四库跨数据集）。

## 二、关键文献与基准数字

| 论文 | 数据 | n（受试者级） | 结果 | 备注 |
|---|---|---|---|---|
| Giancardo 2016, Sci Rep | MIT-CSXPD | 42 PD / 43 HC | digraph 模型 AUC 0.81 | neuroQWERTY 指数奠基作 |
| Arroyo-Gallego 2018, JMIR | 诊所+居家 | 52（25/27） | 诊所 0.83 / 居家 0.76 | 自述样本量小无法性别分层 |
| Adams 2017, PLOS ONE | Tappy | 103（32 轻度 PD） | 声称 AUC 1.00 | **公认过拟合，不可作基准** |
| Tripathi 2023, IEEE TBME | neuroQWERTY 纵向库 | 281（64 确诊） | 确诊组 0.80 / 自报组 0.83；⚠️LR 自报训练→确诊测试 0.81→0.64 | 标签口径混杂的直接证据 |
| Francesconi 2025, arXiv:2510.15950 | 四库 | 33+85+103+230 | 跨库衰减：Tappy→MIT 峰值仅 **0.666**；固定文本→固定文本 0.89–0.91 | 唯一四库打通研究，特征管线模板 |
| Iakovakis 2020, Sci Rep | TyPD+自报库 | 33 临床 + 253 自报 | 临床 0.89–0.97 / 自报降至 0.75–0.79 | 自报标签掉 10–15 个百分点 |

**跨库衰减已被判别力层面量化，覆盖保证层面无人做——这正是本课题的空位。**

## 三、方法学可用资源

- 医学影像有序 CP 模板：Lu, Angelopoulos, Pomerantz, MICCAI 2022（409 例、校准集仅 5% 仍 ~90% 覆盖）；
- CP 入门与规范：Angelopoulos & Bates；Vazquez 2022《CP in Clinical Medical Sciences》；
- 分组条件覆盖陷阱：Rafe 2026（写 limitations 用）；
- Francesconi 2025 的统一特征口径（四信号：hold time / flight time / press-press / release-release）可直接沿用。

## 四、监视名单

- SGC-RML 团队（多模态 PD + conformal，可能扩展打字模态）；
- Francesconi 组（四库管线作者，最可能补 UQ）；
- 每月复扫 `arXiv: "keystroke"+"conformal"` 与 `"typing"+"Parkinson"+"uncertainty"`。
