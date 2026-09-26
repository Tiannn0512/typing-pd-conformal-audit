# Changelog 2026-09-26 ｜ Phase 4 复审轮登记（追加不改写，效力依据：分析冻结协议 v1 效力条款）

来源：2026-09-26 三路复审（A=交叉一致性 / B=预注册合规与泄漏 / C=复现与台账）。
三路总结论均 PASS_WITH_FIXES；结果文件层零缺陷（三脚本逐位重跑复现、naive 锚点三表一致、
零目标域泄漏、零措辞触禁），以下为登记/文档性修复项的正式留存。

---

## §1 CHG-GW1 ｜ group-weighted CP 操作化澄清

- **冻结条文**：plan §4/§11、冻结协议 §6——group-weighted CP（按设备/协议分组，
  作为 remediation benchmark 引用 EJS 2026 框架而非方法贡献）。
- **实现级操作化**：数据无设备元数据 → 分组 = 数据集协议身份（subjects.csv dataset 列）。
  跨库部署几何下源协议与目标协议永不同组、组内密度比不可估 → 实现为**协议组条件分位**
  （组条件/Mondrian 读法：各目标协议用本协议预算的 split 分位）。
  方向 1/2（tappy2mit、mit2tappy）目标为单协议，按构造与 target_recalib 逐位等价
  （代码断言 + CSV note 列如实标注）；方向 3（gold_merged2self，目标含 Tappy BYOD 与
  OE web 两协议）两者不同（5% 预算点估计 0.836 vs 0.876）。
- **性质判定**：注册方法的实现级操作化澄清，非新 CP 变体（复审 B 裁定）；无目标域
  模型选择（预算标签只进分位）。
- **limitations 披露义务（论文）**：group-weighted CP 以协议组条件重校准操作化；
  方向 1/2 与目标域重校准逐位等价——group-weighted 行仅在目标含多协议时有区分力。
- **批准**：预声明于 remediate.py docstring 第 5 条（先于首次运行钉死）；本条为效力
  条款要求的 logs/ 正式登记（复审 B 指出的缺口，本轮关闭）。

## §2 CHG-FD2 ｜ L2/L3 事件基修复的正式登记（追溯补记）

- **内容/证据/批准**：feature_tiers.yaml changelog FEATURE-DEF-2 + key_hand_mapping.yaml
  v1.0.1 变更记录（均用户批准）+ commit 278e631。
- **数字影响**：primary tappy2mit 0.5854→0.5976（K=49/82，q=1.9e-13→1.2e-12）；
  transfer_matrix L2/L3 方向数字更新（详见 TODO 数字勘误 §2/§3）；三方向判定全部不变
  （仍 Incompatible，家族受控）。
- **性质判定**：对冻结定义（digraph_pool、L2=L1+、FEATURE-DEF-1 双手检查）的合规性
  修复，非设计变更；limitations 沿用 TODO-4.1 已知披露项（L2/L3 与 L1 构建来源差异）。

## §3 TODO-4.4 预声明时序补充说明 + 制度修正

- **事实**：七条实现级预声明（remediate.py docstring）与结果同 commit 74e6a1a 入账，
  git 轨迹不能独立证明预声明先于首次运行（TODO-4.3 同构；复审 B CONCERN，不构成
  POL-1 字面违反——无已入库结果被覆盖）。
- **补证记录**：首次运行 20:38；审核 PASS 20:47（独立内存复跑 360/360 单元格逐位一致，
  不依赖项目代码）；commit 20:51:17；docstring 自首次运行未改动（本轮措辞微修后重跑
  CSV 逐位不变验证）。结果含反叙事签名（weighted CP 无用、tappy2mit 30% 内 CI 未恢复），
  无调优动机佐证。
- **制度修正**：防复发制度新增第 4 条——此后实现级预声明先单独 predeclare-commit，
  结果另 commit（TODO_0925.md 防复发制度 §4）。

## §4 待办微修（挂起，下次触碰对应文件时执行）

- TODO_0925.md L769 附近风险预案表"失效图谱首次量化"→"覆盖退化图谱刻画"
  （计划书 §6 risk 2 冻结前原文继承的条件预案；按追加不改写纪律未就地修改，
  以本条防写作期误引）。
