# 分析计划草稿 v0（Analysis Plan — Draft）

> **状态：草稿（DRAFT），W4 冻结。** 本文件从《研究计划书 v1.3.2（执行冻结版）》§2–§4 与《分析冻结协议 v1》抽取而成，作为 TODO-0.3 的预注册草稿底稿。**效力顺序：分析冻结协议 v1 ≥ 研究计划书 v1.3.2 > 本草稿**；W4 冻结时升级为 `docs/analysis_plan_v1.md` 并上传 OSF（TODO-3.4），冻结后任何偏离走变更记录 + 论文 limitations 披露。
> 创建：2026-09-25 20:40 ｜ 创建者：Taylor（TODO-0.3）
> **时序硬约束（自计划书 W4 行）**：本计划冻结**之前**，Tappy→MIT pilot 的任何覆盖数值不得被查看或记录（pilot 仅输出工程 pass/fail）。

---

## 1. 研究问题与中心假设

- **RQ1（库内效度）**：MIT 85 人上，预注册共形管线是否表现预期边际覆盖（split CP 主 + CV+ 敏感性 × α∈{0.05, 0.10} × 校准规模敏感性）。小校准下的全集退化如实报告为发现。
- **RQ2（跨库可靠性，主战场）**：跨库部署偏移下边际覆盖 / 类条件覆盖 / 集合效率 / 判别力相对库内参照如何变化。12 方向全跑，每方向六元组：总体覆盖、PD 类条件覆盖、HC 类条件覆盖、平均集合大小、单例-模糊-空集比例、AUC。
- **RQ3（退化刻画与恢复）**：受控患病率偏移与标签腐蚀**是否足以复现**观察到的覆盖表型；恢复审计阈值以上覆盖需要多少目标域标注（target calibration budget）。
- **H1（可观察假设，预注册）**：判别性能退化与覆盖性能退化在跨库部署偏移下**是否呈现非同一模式（non-identical patterns）**。检验 = 每方向 (ΔAUC, Δ总体覆盖, ΔPD类条件覆盖) 的描述性散点/斜率；**禁止对 12 方向做相关性显著性检验**（非独立、n=12）；禁用 "demonstrate separability" 断言语气。

## 2. 数据与队列

- 四库角色（v1.3 冻结）：MIT-CSXPD 85（临床金标准，合并源池主体 + RQ1 唯一场所）；TyPD 33（金标准，**纯外部应力测试集**，只进 MIT→TyPD 探索性方向，不进任何校准池）；Tappy 227 + Online English 230（自报大池）。
- 合并临床标注源池 = MIT+TyPD 118 人（仅指标签来源/诊断质量合并，**不隐含成分数据集分布可交换**）；仅用于 RQ2 主终点方向 3 的源域。
- **样本数唯一权威口径 = W3 冻结队列表**（raw N → 排除 → eligible N → PD N/HC N → 排除的单纯震颤 N），不沿用引用论文子集数字。
- 清洗规则 label-blind 全预登记（digraph hold/latency ≤0 或 >10s 剔除；固定文本 flight>3s、<20 字符/分剔除；自由文本不清洗；session 有效 digraph<100 剔除；person 有效 digraph<300 排除；Tappy 单纯震颤 3 人主分析排除+双向敏感性；OE H&Y0 保留+敏感性剔除）。
- **不变量：One subject = one conformal observation**——训练/校准/测试全链受试者级隔离；人级分数 = 有效 session 分数中位数（worst-session 敏感性）。

## 3. 特征与模型

- 特征三档（审计控制变量）：L1 = hold/flight/latency 无条件统计（四库通用，TyPD 上限）；L2 = L1+手别条件（MIT/Tappy/OE）；L3 = L2+字符二连键（MIT/OE）。跨库按**目标库**自动降档，档位作为覆盖衰减显式协变量。
- 模型：LightGBM 主 + LR 基线。调参仅源域内部 CV。非共形参照线：bagged LightGBM 方差 + 温度缩放 max-softmax ECE（estimand 不同、无覆盖保证，仅对照）。
- **目标域泄漏防治条款（硬条款）**：**Target datasets are never used for model selection**——目标库不用于任何模型选择（超参/特征档位/迁移方向取舍）；一切目标域适应仅限预先指定的校准程序。

## 4. 共形方法

- 主方法：split conformal（二分类，score = 1 − 真类概率）。敏感性：CV+（理论保证 1−2α，已标注）。探索性（预注册零预期）：weighted CP（密度比加权，权重截断+分布报告）、group-weighted CP（按设备/协议分组，引 EJS 2026 为 remediation benchmark）。
- 校准：源域受试者级分层切分。目标域重校准按预算梯度 **0/5/10/20/30%** 标注（target calibration budget = 一级概念）。

## 5. 三分类判定规则（预注册）

目标域测试集总体覆盖率 Clopper-Pearson 95% CI：
- 下界 ≥ 0.80 → **Compatible（相容）**；
- 上界 < 0.90 → **Incompatible（不相容，覆盖退化证据）**；
- 其间 → **Undetermined（证据不足）**。

> ✅ **重叠区归属已钉死（2026-09-26 用户批准）：Incompatible 优先**——hi < 0.90 →
> Incompatible；否则 lo ≥ 0.80 → Compatible；否则 Undetermined（现行 classify() 即此口径，
> 无需改代码）。理由：与 0.90 主假设对齐、保住主战场检出力（π=0.85 gold_merged2self：
> 0.884 vs 0.214）。拍板前对照模拟已先行入账：scripts/overlap_priority_compare.py +
> results/overlap_priority_compare.csv（commit 18fd308）。v1.3.2 冻结文本的条文顺序读法
>（Compatible 优先）由本条显式取代，limitations 披露。

**判定对象声明**：判定的是"观测覆盖与预设审计阈值的统计相容性"，**不是对真实覆盖失败与否的断言**——标题与结论不得读成"CP 在部署偏移下失败了"。
**阈值定性**：0.80 = pre-specified operational audit threshold（项目预设运行审计阈值），**非临床公认安全阈值**，全文禁用"临床安全阈值"表述。
"相容" ≠ "覆盖维持 90%"，只表示"证据与 ≥0.80 相容"。

## 6. Primary family（预注册主终点）

- 构成：**3 个高功效方向 × α=0.10 × 总体覆盖**：① Tappy→MIT（n=85）② MIT→Tappy（n=227）③ 合并临床标注源池→自报合并（n≈457）。
- 检验：family 内 Holm 校正；H0 = 真实覆盖 ≥0.90 单侧不足；family-wise 0.10；判定基于 Holm 调整后 CI。
- **构成依据**：W4 冻结前完成 per-cell 二项功效模拟表（真覆盖 ∈ {0.90, 0.85, 0.80, 0.70} 的三分类判中概率，TODO-3.3）；若某 primary 方向真覆盖=0.90 时"不可判定"概率 >60% → 该方向降 exploratory（预登记规则）。
- MIT→TyPD（n=33）降为**个案研究**；其余 8 对 **exploratory**（全清单 W4 锁定）。

## 7. 安全性诊断终点（必报，不进 primary family）

- PD/HC 类条件覆盖 = **pre-specified safety diagnostic**，**非分布无关保证**（依据 arXiv:2607.18088：协变量+标签偏移并存时类条件覆盖可能不可识别）。
- 与"仅总体覆盖"的差异显式呈现，支撑"仅总体覆盖不足以支撑部署导向审计"的引言逻辑。

## 8. 效率与部署效用（必报）

- 平均/中位集合大小；单例/模糊/空集比例；覆盖→工作流映射比例（单例=自动通过 / 双例=人工复核 / 全集=系统拒绝）。
- 判别力：受试者级 AUC（分层 bootstrap 1000，CI）；CI 方法：覆盖率 Clopper-Pearson 精确二项。

## 9. RQ3 应力测试（预注册）

- **实验 A（合成剂量-反应 3×3）**：MIT 源域**人级**翻转（分层随机化）：方向 PD→HC / HC→PD / 对称 × 剂量 10/20/30%；与 Einbinder（JMLR 2024）理论对表——理论验证定位。
- **实验 B（真实迁移三方校准对照）**：金域校准直推 / 目标域重校准 / weighted CP。
- **实验 C（降级 BBSE）**：仅合成 label shift 版；真实跨库对只报患病率估计及 CI（描述性）。
- **三臂应力测试**：臂 1 纯重采样（患病率→Tappy 实测 74%）/ 臂 2 纯非对称翻转（保持患病率）/ 臂 3 叠加。判据：整体覆盖 ±5pp、集合大小分布 ±0.3 内复现真实 Tappy 模式。**容差 = pre-specified practical equivalence tolerance**，非统计显著性阈值。
- 注入范围分档：仅校准集翻转 vs 训练+校准同时翻转，以不翻转为基线。
- **结论措辞模板（冻结）**："检验患病率重配与随机标签腐蚀**是否足以复现**观察到的覆盖模式"——不主张因果识别。
- 解释轴：Tappy 字段缺失率 × 覆盖漂移（BirthYear 17.6%、Sided 47.6%、UPDRS 95% "Don't know"）。

## 10. 恢复-代价表（正式结果）

行 = {naive CP, 目标域重校准(5/10/20/30), weighted CP, group-weighted CP}；列 = {所需目标域标注数, 总体覆盖, PD 覆盖, 平均集合大小, 单例率, 拒绝率}。正式回答"跨库部署后需要多少目标域标注才能把覆盖拉回可接受区间"。

## 11. 敏感性分析批（预登记）

α=0.20；Tappy session 切分口径变体；OE H&Y0 剔除；Tappy 震颤 3 人双向计入；特征档位协变量；50 seeds（configs/seeds.yaml split_seeds 1–50）汇总。

## 12. MVP 砍线顺序（预登记，只砍不加）

先砍实验 A（引理论文献）→ 再砍分组审计 → **永不砍**：primary family、PD 类条件覆盖安全终点、恢复-代价表。禁止新增 CP 算法变体、深度模型、新数据集（scope discipline）。

## 13. 结果无条件声明（预注册）

Primary scientific outcomes are not conditioned on observing coverage degradation。三种模式均为有效结果：补救成功=工程答案；补救失败=shift 非简单协变量型的证据；覆盖相容而判别下降=H1 最强支持。课题价值 = mapping reliability behavior，不是 finding failures。

## 14. 报告规范与复现

TRIPOD-AI + CP 四要素报告；OSF 预注册（primary family、三分类规则、容差、砍线顺序全锁定）；合成单元测试三件套（特征复原 / 可交换合成 split CP 覆盖 90%±3σ / 已知密度比 weighted CP 复原）+ MAPIE 对拍（mapie 1.5.0 SplitConformalClassifier）；git tag `v1.0-prereg`（W4）与 `results-frozen-v1`（W9）。

## 15. 措辞禁令（全文适用）

禁：first CP for typing-PD ｜ NexCP audit ｜ "PD 数字表型的 CP 可靠性未被研究" ｜ "分布偏移下 CP 审计"宽口径 first ｜ "首次证明 CP 在 PD 中失效" ｜ "可接受临床覆盖阈值"。

## 16. 局限声明（预注册）

自报库覆盖结论限定 estimand；随机翻转 ≠ 结构化自报噪声（复现结论限定"足以复现"）；TyPD n=33 不可判定为预期；MIT 对照组女性偏多 17pp（分组审计显式报告）；合并源池可交换性声明（合并仅指标签来源质量）。

## 17. W4 冻结前待完成清单

- [ ] TODO-3.1 合成单元测试三件套 + MAPIE 对拍通过
- [ ] TODO-3.2 MIT 库内基线 AUC ∈ [0.75, 0.91]（go/no-go）
- [ ] TODO-3.3 先验功效模拟表落盘（primary family 构成依据，降级规则执行）
- [ ] Tappy→MIT pilot 工程冒烟（覆盖数值不可见）
- [ ] 本草稿升级为 `docs/analysis_plan_v1.md`（exploratory 组全清单锁定）→ OSF 注册 → DOI → `git tag v1.0-prereg`
