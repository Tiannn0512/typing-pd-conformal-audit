# QC 报告 — Phase 2 清洗后分析就绪数据（TODO-2.2）

**生成**：2026-09-26 11:15 ｜ **配置**：configs/cleaning.yaml ｜ **权威队列表**：results/cohort_flow.csv（eligible=475：PD 270/HC 205）

## 1. 特征缺失率（Tier-A = L1 三信号 15 列）

| 特征列 | 缺失数 | 缺失率 |
|---|---|---|
| L2tappy_hold_L_mean | 302 | 63.6% |
| L2tappy_latency_L_mean | 302 | 63.6% |
| L2tappy_flight_L_mean | 302 | 63.6% |
| L2tappy_hold_R_mean | 302 | 63.6% |
| L2tappy_latency_R_mean | 302 | 63.6% |
| L2tappy_flight_R_mean | 302 | 63.6% |

L1 15 列中 15 列零缺失；L1 最大缺失率 = 0.0%（gate：<50% → PASS）。L2tappy 6 列仅 Tappy 行（173/475）非空，属设计内档位差异，不计缺失。

## 2. 零方差列

L1 零方差列：无

## 3. 性别分布（分组审计预备）

| 数据集 | 字段可得性 | 分布 |
|---|---|---|
| mit | **本数据无性别字段**（GT 列不含 Gender）| 文献口径照抄：对照组女性偏多 ~17pp（可行性报告 §四；计划书局限声明已冻结）——分组审计按文献口径预备 |
| tappy | 有（自报）| {(False, 'Female'): 18, (False, 'Male'): 22, (True, 'Female'): 67, (True, 'Male'): 66} |
| typd | 有（临床）| {(False, 'Female'): 7, (False, 'Male'): 8, (True, 'Female'): 1, (True, 'Male'): 11} |
| oe | **本数据无性别字段** | 不可得（在线招募未含性别入公开 CSV）|

## 4. session 数分布（每人，存活 session）

| 数据集 | session 定义 | min | 中位 | max |
|---|---|---|---|---|
| mit | visit 文件 | 1 | 1 | 1 |
| tappy | 月文件（USER_YYMM） | 1 | 2 | 10 |
| typd | visit（全部 TEX trial 合并评估，CHG-1） | 1 | 1 | 1 |
| oe | participant×response | 3 | 11 | 14 |

**Tappy 月文件切 session 口径记录**：session = 自然月文件（USER_YYMM），同一人跨月多 session 属设计内（自然打字纵向流）；tappy 为自由文本，flight/速率规则豁免，仅适用 digraph 通用规则 + valid<100。

## 5. person 有效 digraph 分布

- mit: min=370 / median=1245 / max=2816
- tappy: min=328 / median=8086 / max=1072437
- typd: min=493 / median=759 / max=960
- oe: min=319 / median=1305 / max=2954

**观察**：Tappy 有 24 名用户有效 digraph >10 万（最大 1,072,437，约占 Tappy 总量 12%）——person 级聚合下每人一行不受影响，但 Phase 4 涉及 Tappy digraph 总量口径的统计时须注意该长尾。

## 6. Gate 检查

- [x] 无 Tier-A 特征缺失 >50%：PASS（最大 0.0%）
- [x] MIT 性别失衡（对照女多 17pp，文献口径）已显式记录（§3；本数据无 MIT 性别字段，分组审计按文献口径预备——与计划书局限声明一致）