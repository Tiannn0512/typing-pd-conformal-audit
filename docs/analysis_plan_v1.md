# 分析计划 v1.0（Analysis Plan — FROZEN）

## 帕金森打字检测中共形覆盖的系统性跨库审计：判别鲁棒与不确定性鲁棒的模式刻画

> **状态：冻结（FROZEN v1.0）** ｜ 冻结时间：2026-09-26 ｜ 冻结者：Taylor
> 本文件为 OSF 预注册正文（TODO-3.4）。效力顺序：**本文件（冻结版）≥ 分析冻结协议 v1（含
> CHG-P1 变更）≥ 研究计划书 v1.3.2**。冻结后任何偏离须在 `logs/` 留变更记录并在论文
> limitations 报告。签署：分析冻结协议 v1 已于 2026-09-26 随 CHG-P1 登记签署（见该文件
> 变更记录节与本文件 §16）。
> **时序声明**：本冻结先于任何跨库覆盖数值的查看（Tappy→MIT pilot 仅输出工程 pass/fail，
> 其覆盖数值在冻结前不可见、不可记录——TODO-3.5 时序硬约束）。

---

## 1. 研究问题与中心假设

- **RQ1（库内效度）**：MIT 82 人（冻结队列表口径）上，预注册共形管线是否表现预期边际覆盖（split CP 主 + CV+ 敏感性 × α∈{0.05, 0.10} × 校准规模敏感性）。小校准下的全集退化如实报告为发现。
- **RQ2（跨库可靠性，主战场）**：跨库部署偏移下边际覆盖 / 类条件覆盖 / 集合效率 / 判别力相对库内参照如何变化。12 方向全跑，每方向六元组：总体覆盖、PD 类条件覆盖、HC 类条件覆盖、平均集合大小、单例-模糊-空集比例、AUC。
- **RQ3（退化刻画与恢复）**：受控患病率偏移与标签腐蚀**是否足以复现**观察到的覆盖表型；恢复审计阈值以上覆盖需要多少目标域标注（target calibration budget）。
- **H1（可观察假设，预注册）**：判别退化与覆盖退化在部署偏移下**是否呈现非同一模式**。检验 = 方向级 (ΔAUC, Δ总体覆盖, ΔPD类条件覆盖) 描述性散点/斜率；**禁止对 12 方向做相关性显著性检验**（非独立、n=12）；禁用 "demonstrate separability" 断言语气。

## 2. 数据与队列（冻结）

- 四库角色：MIT-CSXPD（临床金标准，合并源池主体 + RQ1 唯一场所）；TyPD（金标准，**primary/合并链路中纯外部**：不进 primary 三方向与合并池方向的任何校准池，个案研究 MIT→TyPD 保持 TyPD 纯外部）；Tappy + Online English（自报大池）。
  **TyPD 在 12 方向矩阵中的读法（v1.0.1 钉死）**：exploratory 的 TyPD-源方向（typd→mit/tappy/oe）使用 TyPD 内部校准（源域内部切分，与其他源一致），结果按 exploratory 如实报告——此为计划书 §2"12 方向全跑"的题中之义；"纯外部"条款管辖范围限定于 primary/合并/个案链路。
- 合并临床标注源池 = MIT+TyPD（仅指标签来源/诊断质量合并，**不隐含成分数据集分布可交换**）；仅用于 RQ2 主终点方向 3 的源域。
- **样本数唯一权威 = W3 冻结队列表**（results/cohort_flow.csv）：**eligible=475（PD 270/HC 205）**——MIT 82（42/40）、Tappy 173（133/40；无标签 29、单纯震颤 3 出队）、TyPD 27（12/15）、OE 193（83/110）。清洗 label-blind 全预登记（configs/cleaning.yaml，含 CHG-1）。
- **不变量：One subject = one conformal observation**；人级分数 = 有效 session 分数中位数（worst-session 敏感性）。session 唯一性已在管线断言；session 级辅助分析须实测 ICC 与设计效应并标注 estimand。**全量 cell 结果公开**（primary/exploratory/个案无遗漏）。

## 3. 特征（冻结 + W4 预声明）

- 三档体系（configs/feature_tiers.yaml）：L1 = hold/latency/flight × {mean, median, sd, p10, p90}（四库）；L2 = L1 + 手别条件（MIT/Tappy/OE）；L3 = L2 + 字符二连键（MIT/OE）。
- **手别映射表 v1.0.0 已冻结**（configs/key_hand_mapping.yaml，2026-09-26 用户批准；标准美式 QWERTY 指法分区；空格/特殊键不硬归属、L2 内剔除并计数；OE 上档字符按基准键手别；不可映射键剔除计数）。Tappy 用原生手别列；TyPD L1 上限（schema 机器断言）。
- 跨库按目标库降档：tier(方向) = min(max_tier(源), max_tier(目标))；**特征档位作为覆盖衰减的显式协变量记录**。
- **W4 预声明（不可逆，用户批准 2026-09-26）**：MIT L2/L3 完整特征补充基线将作为**补充参照**纳入预注册后的报告；**无论其结果如何，TODO-3.2 的 gate 判定不重开、主参照不翻回**（见 §4/协议 CHG-P1）。

## 4. 模型（冻结 + CHG-P1 修正）

- **有效主参照模型 = 逻辑回归**（StandardScaler 仅训练折内 fit；官方默认参数）——协议 §3 经 CHG-P1 修正（2026-09-26 用户批准）：LightGBM 三轮 gate FAIL 证据链（0.5000 机制性退化 / 0.7067 单分裂 / 0.7257 微网格 val 选择）vs LR 0.7868 带内（≈文献锚点 0.80-0.81），三轮留档 results/baseline_mit_run{1,2,3}_*.csv。
- LightGBM 为**对照模型**同表披露（min_child_samples=10 微网格 val 选择，DEC-B3b）。
- 非共形参照线：bagged LightGBM 方差 + 温度缩放 max-softmax ECE（estimand 不同、无覆盖保证）。
- **目标域泄漏防治（硬条款）**：Target datasets are never used for model selection——目标库不用于任何模型选择；一切目标域适应仅限预先指定的校准程序。

## 5. 共形方法（冻结）

- 主方法：**split conformal**（二分类，score = 1 − 真类概率；k = ⌈(n+1)(1−α)⌉ 有限样本校正；实现 src/cp/conformal.py，与 MAPIE 1.5.0 逐点一致 1800/1800）。
- 敏感性：CV+（理论保证 1−2α，已标注）。探索性（预注册零预期）：weighted CP（密度比权重；实现 = Tibshirani 2019 式(8) 直接形式，经 6-regime 独立 oracle 逐点对拍与 w≡1≡split 守卫——2026-09-26 复发猎杀后终版；**权重截断 + 权重分布报告**为预登记细节）、group-weighted CP（按设备/协议分组，引 EJS 2026 为 remediation benchmark）。
- 校准：源域受试者级分层切分；目标域重校准按预算梯度 **0/5/10/20/30%**（target calibration budget = 一级概念）。

## 6. 三分类判定规则（预注册，含重叠区钉死）

目标域测试集总体覆盖率 K/n 的 Clopper-Pearson 95% CI：
1. 若 **hi < 0.90 → Incompatible（不相容，覆盖退化证据）**；
2. 否则若 **lo ≥ 0.80 → Compatible（相容）**；
3. 否则 → **Undetermined（证据不足）**。

- **重叠区归属（已钉死，2026-09-26 用户批准）**：{lo ≥ 0.80 且 hi < 0.90} 归 **Incompatible**。理由：与 0.90 主假设对齐、保住主战场检出力（π=0.85 gold_merged2self 方向检出力 0.884 vs Compatible 优先的 0.214）。拍板前对照模拟已入账（scripts/overlap_priority_compare.py + results/overlap_priority_compare.csv，commit 18fd308）；v1.3.2 条文顺序读法由本条显式取代，limitations 披露。
- **判定对象声明**：判定的是"观测覆盖与预设审计阈值的统计相容性"，**不是对真实覆盖失败与否的断言**。
- **阈值定性**：0.80 = pre-specified operational audit threshold（项目预设运行审计阈值），**非临床公认安全阈值**；"相容" ≠ "覆盖维持 90%"。
- **结果无条件声明（预注册）**：Primary scientific outcomes are not conditioned on observing coverage degradation——三种判定（相容/不相容/证据不足）均为有效科学结果：补救成功=工程答案；补救失败=shift 非简单协变量型的证据；覆盖相容而判别下降=H1 最强支持。课题价值是 **mapping reliability behavior**，不是 finding failures。

## 7. Primary family（预注册主终点）

- 构成：**3 方向 × α=0.10 × 总体覆盖**：① Tappy→MIT（n=85）② MIT→Tappy（n=227）③ 合并临床标注源池→自报合并（n≈457）。
- 检验：family 内 **Holm** 校正；H0 = 真实覆盖 ≥0.90 单侧不足；family-wise 0.10；**判定基于 Holm 调整后 CI**。
- **构成依据（功效模拟，已完成；双口径）**：计划书口径 results/power_table.csv（n=85/227/457/33）与**冻结队列表口径 results/power_table_frozen_n.csv（n=82/173/366/27——主判定依据）**；各 50,000 reps/cell，seed=20260925。冻结 n 下 π=0.90 时 P(Undetermined) = 28.6% / 1.6% / 0.0%，全部 < 60% 降级阈值 → **零降级**，family 维持三方向（计划书 n 口径方向一致：32.1%/0.0%/0.0%）。前向注记：Holm 调整后实际 P(Undetermined) ≥ 表列边际值（tappy2mit 28.6% 为下界），判读按预登记规则处理。
- MIT→TyPD（冻结 n=27；功效模拟输入 n=33）= **个案研究**（模拟显示 P(Undetermined) 75.3%/84.2%，与冻结局限声明一致）；其余 **9 方向** = **exploratory**（全清单 §13）。

## 8. 安全性诊断终点（必报，不进 primary family）

PD/HC 类条件覆盖 = pre-specified safety diagnostic，**非分布无关保证**（依据 arXiv:2607.18088）；与总体覆盖差异显式呈现。

## 9. 效率与部署效用（必报）

平均/中位集合大小；单例/模糊/空集比例；覆盖→工作流映射（单例=自动通过 / 双例=人工复核 / 全集=系统拒绝）；受试者级 AUC（分层 bootstrap 1000）；覆盖率 CI = Clopper-Pearson 精确二项。

## 10. RQ3 应力测试（预注册）

- **实验 A（合成剂量-反应 3×3）**：MIT 源域人级翻转（分层随机化）：方向 {PD→HC, HC→PD, 对称} × 剂量 {10, 20, 30}%；与 Einbinder（JMLR 2024）理论对表。
- **实验 B（真实迁移三方校准对照）**：金域校准直推 / 目标域重校准 / weighted CP。
- **实验 C（降级 BBSE）**：仅合成 label shift 版；真实跨库对只报患病率估计及 CI（描述性）。
- **三臂应力测试**：臂 1 纯重采样（患病率→Tappy 实测 74%）/ 臂 2 纯非对称翻转（保持患病率）/ 臂 3 叠加；判据：整体覆盖 ±5pp、集合大小分布 ±0.3 内复现真实 Tappy 模式；**容差 = pre-specified practical equivalence tolerance**（非统计显著性阈值）。
- 注入范围分档：仅校准集翻转 vs 训练+校准同时翻转，以不翻转为基线。
- **结论措辞模板（冻结）**："检验患病率重配与随机标签腐蚀**是否足以复现**观察到的覆盖模式"——不主张因果识别。
- 解释轴：Tappy 字段缺失率 × 覆盖漂移（BirthYear 17.6%、Sided 47.6%、UPDRS 95% "Don't know"）。

## 11. 恢复-代价表（正式结果）

行 = {naive CP, 目标域重校准(5/10/20/30), weighted CP, group-weighted CP}；列 = {所需目标域标注数, 总体覆盖, PD 覆盖, 平均集合大小, 单例率, 拒绝率}。

## 12. 敏感性分析批（预登记）

α=0.20；Tappy session 切分口径变体；~~OE H&Y0 剔除~~（**不适用**：公开数据无 H&Y 字段，主分析保留全部自报 PD——与 Tappy UPDRS 字段不可用同性质）；Tappy 震颤 3 人双向计入；特征档位协变量；50 seeds（split_seeds 1–50）汇总。

## 13. Exploratory 组全清单（锁定）

12 有序方向（4 库两两）中扣除 primary（tappy2mit、mit2tappy）与个案研究（mit2typd）后的 **9 方向**：
`tappy→typd, tappy→oe, typd→mit, typd→tappy, typd→oe, oe→mit, oe→tappy, oe→typd, mit→oe`。
外加合并池方向 1 个（primary③）。exploratory 方向结果全部如实报告（含不可判定），不进 family、不做 Holm。

## 14. MVP 砍线顺序（预登记，只砍不加）

先砍实验 A（引理论文献）→ 再砍分组审计 → **永不砍**：primary family、PD 类条件覆盖安全终点、恢复-代价表。禁止新增 CP 算法变体、深度模型、新数据集（scope discipline）。

## 15. 报告规范与复现

TRIPOD-AI + CP 四要素；本文件 = OSF 预注册正文；合成单元测试三件套（特征复原 / 可交换 split CP 覆盖 90%±3σ 实测 0.9000 / weighted 式(8) 独立 oracle 6-regime 逐点一致）+ MAPIE 对拍（1800/1800）已在冻结前完成（18/18 测试）；git tag `v1.0-prereg`（W4）与 `results-frozen-v1`（W9）；一键重跑（W12）。

## 16. 既有变更记录（冻结时点汇总，均用户批准）

| ID | 内容 | 日期 |
|---|---|---|
| CHG-1 | TyPD session 粒度 trial→visit（协议未定义粒度的实现澄清；digraph 派生仍限 trial 内） | 2026-09-26 |
| CHG-P1 | 协议 §3：有效主参照 = 逻辑回归（LGBM 三轮 gate FAIL 证据链；LR 0.7868 带内）| 2026-09-26 |
| DEF-1 | OE 重复行保留原样 + limitations（2,063 参与/1,203 冗余，占 keep 行 0.27%） | 2026-09-26 |
| 重叠区钉死 | Incompatible 优先（对照模拟先行入账 commit 18fd308） | 2026-09-26 |
| W4 预声明 | L2/L3 补充基线为补充参照；gate 不重开、主参照不翻回（不可逆） | 2026-09-26 |
| POL-1 | 轮次留档、不无痕覆盖制度 | 2026-09-26 |
| v1.0.1 补丁 | 双口径 n 调和（补 power_table_frozen_n.csv）｜"其余 9 方向"勘误｜TyPD 12 方向矩阵读法钉死｜结果无条件声明补回｜weighted 权重截断+分布报告补回｜ICC/全量 cell 条款补回（审核门五必修+建议闭环） | 2026-09-26 |

## 17. 措辞禁令（全文适用）

禁：first CP for typing-PD ｜ NexCP audit ｜ "PD 数字表型的 CP 可靠性未被研究" ｜ "分布偏移下 CP 审计"宽口径 first ｜ "首次证明 CP 在 PD 中失效" ｜ "可接受临床覆盖阈值"。

## 18. 局限声明（预注册）

自报库覆盖结论限定 estimand；随机翻转 ≠ 结构化自报噪声（复现结论限定"足以复现"）；TyPD n=33 不可判定为预期；MIT 对照组女性偏多 17pp（文献口径，本数据无性别字段）；合并源池可交换性声明；OE 原始 232 人 vs 文献 230（分析子集数不沿用）；Tappy 可入队上限 217；OE keep 行 latency≤0 占 18.85%（82,537）；CHG-P1 主参照修正与三轮运行史；DEF-1 保留重复（0.27%）；重叠区 Incompatible 优先取代条文顺序读法；weighted CP 无第三方库对拍（MAPIE 无协变量偏移 weighted），正确性由独立 oracle 保证。
