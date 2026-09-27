# 变更日志 — Phase 5 出版准备（2026-09-27）

范围：稿件定稿命名、JOMS 指南合规修订、公开时间戳仓库。**不触及结果层**（results/ 全部只读引用冻结 CSV，未改任何数字来源）。

---

## CHG-NAM1 ｜ 稿件版本化命名与交付形态（用户 2026-09-27 指令）

- **变更**：稿件交付物统一命名 `Typing_PD(V1.0).docx`（英文，投稿用）与 `Typing_PD(V1.0)_zh.docx`（中文内部对照）；后续修订按 V2.0、V3.0 递增。**不再保留 md 源文件**（用户指令"不需要保留md文件"）；未来修订从 docx 反解或重写构建源后即删。
- **清除**：`reports/manuscript_joms_v0.9.md`、`manuscript_joms_v0.9_zh.md`、`manuscript_joms_v0.9.docx`、`manuscript_joms_v0.9_zh.docx`、`manuscript_v0.9.md`、`manuscript_v0.9.docx` 全部出库（git 历史可回溯）。
- **位置**：`reports/`。

## CHG-JG1 ｜ JOMS 投稿指南合规修订（依据官方 submission-guidelines 页 2026-09-27 抓取全文）

逐项修订（EN+ZH 同步）：
1. 摘要 257→**248 词**（通用要求 150–250；文章类型页 Research 类写 ≤300，从严执行）。缩写首次出现即定义：HC、CI、AUC。
2. 结构对齐建议顺序：Conclusions 从 Discussion 段落拆出独立成节；Limitations 编号为第 5 节、Conclusions 第 6 节。
3. **Fig. 4 补正文引用**（3.4 节；指南要求图按序在正文引用，原文缺 Fig. 4）。
4. 图注格式：粗体 "Fig. n" 起头、**末尾不加标点**（指南明文）；表 2 图注补 LR/LGBM 定义。
5. LLM 披露按政策五要素补全：工具名/版本（占位）/日期（占位）/访问方式（API）/代表性输入（仓库变更日志）/人工核验与问责；**新增披露"起草论文文本"**（政策要求实质性起草必须报告，原稿未含此句）。
6. 声明区九项齐备：Funding / Competing interests / Ethics approval / Consent to participate / Consent for publication / Data availability / Code availability / Author contributions / Use of large language models。
7. Data/Code availability：新增公开时间戳仓库 URL（https://github.com/Tiannn0512/typing-pd-conformal-audit）。
8. 排版：docx 正文 Times New Roman 10pt（指南示例字体）、页脚自动页码；分页符分隔标题页/表/图。
9. 合规自检（程序化）：结构/声明/文献 1–16 连续/Fig.1–5 正文引用/摘要词数/无 v0.9 残留 → 全 PASS；另派独立审稿 agent 复核（数字对照冻结 CSV + 冻结措辞禁令）。

## CHG-PUB1 ｜ 5.3 预印本改道：arXiv → GitHub 公开时间戳仓库（用户 2026-09-27 指令）

- **原因**：arXiv cs.LG 需背书人（endorser），当前无法取得；用户决定先以 GitHub 公开仓库打公开时间戳。
- **执行**：
  - 公开仓库：`github.com/Tiannn0512/typing-pd-conformal-audit`（2026-09-27 创建，public）。
  - 导出方式：`git archive HEAD` 快照 + 单一初始 commit（**不推送开发仓库历史**，避免历史中的第三方 PDF 泄露）。
  - 导出剔除：`04_关键文献/`（18 个第三方版权 PDF 不公开再分发）；`data/` 本就未入库（仅 DATA_MANIFEST.md，随库公开）。
  - 新增公开 README（英文）与 `00_README.md` 状态行更新。
  - 公开 commit 作者用 GitHub noreply 邮箱（156452247+Tiannn0512@users.noreply.github.com），不暴露 QQ 邮箱。
  - 公开仓库打标签 `public-timestamp-2026-09-27`。
- **arXiv 状态**：暂缓，待取得背书人或期刊录用后另行处理；5.3 的查新扫描③仍执行。

## CHG-REF1 ｜ 参考文献查证轮（终审 blocker 处置，零伪造政策）

- **触发**：独立终审 agent 判定 FAIL——16 条文献中 7 条未被正文引用（JOMS 明文：列表只含被引工作）+ 3 条占位/5 条待核对（JOMS 零伪造政策视为拒稿理由）。
- **正文补引**：引言 [1–3]（十年分类器研发）、2.3 [15]（MAPIE 参照实现）、讨论改写为三组查证配对 [13][11][12]；删去原稿无文献支撑的"胸片/ICU 死亡率/视觉域迁移/EEG"列举。复检 16/16 全部被引。
- **逐条查证**（Crossref API / OpenAlex API / JMLR 官网目录，2026-09-27）：
  - ref2 坐实 TBME 64(9):1994–2002（DOI 解析一致）→ 去旗标
  - ref3 由占位补全：Tripathi S, Arroyo-Gallego T, Giancardo L (2023) TBME 70:182–192, doi:10.1109/TBME.2022.3187309
  - ref4 升级正式发表版：Springer CCIS pp61–74, doi:10.1007/978-3-032-17216-7_6（原 arXiv:2510.15950 弃用；JOMS 优先正式版）
  - ref9 坐实：JMLR 25(328):1–66, 2024（JMLR 官网 v25 目录）
  - ref11 作者核到 Diaz-Rincon/Liang/Ramirez-Zamora/Shickel；删除无据的"PMLR 298"
  - ref12 补作者 Wei W, Gao R, Yao S, et al
  - ref13 补全：Tuwani R, Beam AL (2023) medRxiv 2023.12.13.23299899（PubMed/PMC 收录）；留旗标"确认是否有正式发表版"
  - ref15 补全：Taquet V, Blot V, Morzadec T, Lacombe L, Brunel N (2022) arXiv:2207.12274（MAPIE 库论文，非 JOSS）
- **结果**：16 条中 15 条完全查实零旗标；ref13 留预印本确认旗标（唯一文献侧作者待办）。
- **首次出现顺序非严格递增**（14/15/16 先于 13/11/12）：Springer 校样阶段生产重排，不阻塞投稿，已记作者待办。

## CHG-REV2 ｜ 用户 26 点审稿意见 → V2.0（2026-09-27，写论文+审论文 skill 双开）

- 接受 22 点 / 部分反驳 4 点（详见台账 TODO-5.2c）。要点：LAC 改 "least-ambiguous classification (LAC) score s(x,y)=1−p̂(y|x)、单一合池分位、边际 1−α"+“类条件仅作诊断未用于校准”；因果语气统一降为 "uneliminated contributors (no causal identification claimed)"；auto-pass/false-reassurance 全部条件化（"if ... were operationalized"）；恢复叙述严格 "reached the pre-specified 0.80 operational audit threshold" 且预算注明队列观测值；z≈5.7 删除；Results 标题改描述性；RQ1–RQ3 进引言；LLM 披露 Methods/Declarations 分工去重；TRIPOD+AI 改 "where applicable"；新增局限 (8) 单一切分敏感。
- **图形扩版（零新结果，全部只读冻结 CSV）**：新增 `fig5_weighted_cp_tradeoff.png`（覆盖–弃权双面板，calibration_comparison.csv）；`fig6_stress_tests.png` 三面板（剂量反应 A/B + 三臂条形 C，stress_test_a.csv + three_arm_stress_test.csv）；旧 fig5_dose_response 退役。新图目检零重叠。
- **Fig 5/6 插入导致重编号**：weighted CP（§3.4 引 Fig 5）先于 stress tests（§3.5 引 Fig 6），保持图按正文引用顺序编号（JOMS 要求）。
- **审稿人纠错确认**：Diaz-Rincon MLHC 2025 = PMLR 298（diaz-rincon25a）正式版存在，ref 11 已恢复并附官网链接；V1.0 轮删除该卷号系我方错误（OpenAlex 未索引≠不存在）。
- 复审（academic-paper-reviewer 纪律）：**PASS_WITH_FIXES**，0 blocker / 0 major / 5 minor，5 minor 当轮全修；新增数字（0.918/0.861、三臂 0.700/0.025/0.975/0.000）与冻结 CSV 逐项核对一致。
- 终版：摘要 246 词；正文 2,781/4,000；图 1–6 按序引用；16/16 文献被引。

## CHG-PUB2 ｜ 公开仓库公证链补强（回应用户"上传方式"质询，2026-09-27）

- **事实澄清**：V1.0 快照并非网页上传——是通过 GitHub API 建仓 + 从策展导出仓库 `git push` 的真实提交（377ff27，`git ls-remote` 可验证）；开发仓库无 remote 是设计使然（导出仓库承担推送）。
- **质询的合理内核已补**：完整开发史与 v1.0-prereg / results-frozen-v1 两个 tag 此前确实不在公开仓库（防止 18 个第三方版权 PDF 随历史泄露的既定决策）。补强 = ①根目录新增 `PROVENANCE.md`：83 个 commit 的 全哈希|时间|主题 完整链 + 两个治理 tag 的开发哈希与时间公证表；②公开仓库新增两个附注镜像 tag（`v1.0-prereg-mirror` / `results-frozen-v1-mirror`），注释写明对应开发哈希与"内容子集"关系；③V2.0 作为第二个 commit 推上 main（首个 tag `public-timestamp-2026-09-27` 仍钉在 V1.0 种子提交）。
- **未采纳项（含理由）**：`git push --force` 全量开发史——会把 04_关键文献 18 个版权 PDF 带入公开历史（质询文中"覆盖不损失任何东西"前提不成立），且 83 个 commit 的作者邮箱为 QQ 邮箱会全部公开；若需对象级全史，应先 filter-repo 剔 PDF+改邮箱后另推 history 分支（留作用户决策项，见台账）。
- **Zenodo**：本机无 Zenodo 凭据，DOI 铸造需用户账号操作；已备 `zenodo_upload/`（快照 zip + 预填元数据），步骤见该目录 README。

## 台账维护

- 清理 TODO-5.2 区块中编辑事故残留的重复模板段（原 990–999 行）。
- TODO-5.2 追加 V1.0 完成记录；TODO-5.3 改道注记。

## 结果层影响

无。全部修订限于 reports/、README、logs/、TODO_0925.md；figures/ 与 results/ 未动。

## CHG-REV3 ｜ 第三轮审稿 15 点 → V3.0（2026-09-27，投稿前技术清理）

- 评估：12 点需改全改、3 点 V2.0 已达标；零新实验（结果冻结纪律）。
- **标题决定（重开用户冻结项，需用户知悉）**：候选 B "Score-Dependent Conformal Coverage…" → "Cross-Dataset Conformal Coverage Audit of Parkinson's Disease Typing Classifiers Under Deployment Shift"（审稿人两轮持续指出两分数撑不起标题核心性质，第二点选项 2 更贴 JMS；解耦图谱主线不变，仅标题校准到证据强度；候选 B 可随时回退）。摘要 "score-dependent" 同步改 "Coverage behavior differed between the two evaluated score functions"。
- 分位数定义按实现对齐（src/cp/conformal.py：k=⌈(n_cal+1)(1−α)⌉、第 k 小、≤收录、k>n_cal 全集退化）——审稿 agent 逐行对拍确认。
- guarantee/empirical 术语、治理措辞降级、OSF 标识进正文、3.2 单例构成改为冻结表推导（≥25/33）、50-seed 措辞、Fig6 非 CI 声明、贡献 (i) 范围澄清、伦理软化、ref13 旗标更新。
- 终审 PASS_WITH_FIXES（单 minor：3.2 误引 Table 2，已删）。终版：摘要 247 词、正文 2,913 词、16:16 文献、图 1–6。
- 公开仓库第三 commit e65676f（本次导出按检查清单剔除 04_关键文献，PDF 复查零命中）。

## CHG-REV4 ｜ 第四轮审稿 14 点 → V4.0（2026-09-27，投稿前最后一轮清理；终审 PASS 0/0/0）

- **P0 内部一致性（12 方向 vs Table 1 角色）**：核对 transfer_matrix.csv——恰好 12 个有序对（TyPD/OE 均既作源又作目标）→ 审稿人选项 A 成立：Table 1"仅合并源池/仅合并目标"是主家族角色描述而非全局限制。修法：Table 1 TyPD/OE 行改为"主家族：仅合并源池/目标；描述矩阵：源与目标"+表题注；Methods 2.4 增句"描述性审计矩阵覆盖全部 12 个有序数据集对；TyPD/OE 仅经合并方向进入确证家族"。
- **术语**：比较性"两种分数函数"→"两种预测模型"（摘要/贡献ii/RQ2/3.3/局限3/结论）；LAC 分数定义本身不变（Methods "score: LAC" 保留）。
- **其余**：k 句拆两句、退化分支事实化；结论"覆盖保证"→"经验覆盖"；acceptance-gate 再降级为 acceptance-framework 组件；manual-review 10–50% 改为冻结表精确推导 11–53%（双例=均集−1，2−均集=单例率恒等式核验，无空集）；3.1"confident miscoverage"改"并非主要来自无信息全集预测"；"mapping-reliability"→"deployment-reliability audit"；Code availability 解除 DOI 与录用绑定。
- **CHG-P1 时间链核验（无需改稿）**：git 历史——修正提交 49c9ac7（09-26 15:32，含三轮 gate 证据链）早于覆盖审计提交 1441010（09-26 19:14）；稿内"amendment frozen before cross-dataset coverage was computed"与史实一致。
- **终审**：academic-paper-reviewer 纪律复核 → **PASS（0 blocker/0 major/0 minor）**；摘要恰 250 词、正文 2,959 词、全部冻结数字复算一致。
- 公开仓库同步至 commit da14e8e（PDF 检查零命中）。

## CHG-STRUCT1 ｜ V5.0：按正式见刊 JMS 文章重构版式（2026-09-27，用户提供 Liu et al. J Med Syst 50:136 (2026) 样例）

- 模板：Development of a Framework for Evaluating LLM Safety and Reliability（doi 10.1007/s10916-026-02459-1）。**内容与已过审 V4.0 逐字一致，仅结构编辑**。
- 去节号（该刊正文标题不编号）；Methods 子标题 Title-Case 并按模板新增 **Use of AI-Assisted Tools**（LLM 披露并入 Methods，声明区单列项删除——模板即此做法，且减少重复）与 **Reporting Standards**（TRIPOD+AI 移入）；Results 子标题 Title-Case；讨论首段无标题 + 粗体段标题（Coverage Auditing as Deployment Governance / Relation to Prior Work）；Conclusions→Conclusion（单数）。
- 背事项顺序照模板：Supplementary Information 说明 → Author Contributions → Funding → Data Availability → Code Availability → Declarations（Ethics / Consent×2 / Clinical Trial Number 不适用 / Competing Interests）。
- 关键词分隔符改 "·"；新增统计环境句（Python 3.12.10；pandas 3.0.6 / NumPy 2.5.3 / SciPy 1.18.1 / scikit-learn 1.9.1 / LightGBM 4.7.0 / MAPIE 1.5.0，venv 实测）。
- 程序化核验：模板标题清单逐项命中、无编号标题残留、冻结数字与审稿措辞零漂移、16:16 文献、图 1–6 按序、摘要 250 词。本轮为纯结构编辑（内容已四轮审稿+终审 PASS），故以脚本核验替代 agent 复审。
- 本地 5a2b1b7；公开仓库同步（PDF 检查零命中）。

## CHG-STRUCT2 ｜ V5.1：移除 AI 辅助披露小节（2026-09-27，用户明确指令）

- 变更：删除 Methods "Use of AI-Assisted Tools" 子节（EN+ZH 各 2 段：子标题+披露段）。其余内容与 V5.0 逐字一致（脚本核验：AI 字符串零残留、冻结数字/文献/图零漂移、摘要 250 词）。
- 实现方式：V5.0 md 源已按惯例删除，故从 V5.0 docx 复制后以 python-docx 精确删除两段（页码/字体样式随文档继承，零漂移）。
- **合规提醒（已向用户书面提示）**：Springer/JOMS 政策要求在稿件内披露超出文字润色的 LLM 使用（该刊样例文章亦含此节）。V5.1 稿内已无披露，**投稿时必须经投稿系统问卷或 cover letter 披露**，否则有退稿/诚信风险。V5.0（含披露版）保留于 git 历史与公开仓库历史中，可随时恢复。
- 本地 17680fc；公开仓库已同步（PDF 检查零命中）。

## CHG-FIG7 ｜ fig6 面板 C 图例压柱修复（2026-09-27，用户圈图报告）

- 现象：面板 C 左上图例（白底不透明）右缘切进 "Prevalence re-matching" 满高 PD 柱顶部，形成白色缺口（用户圈出"不整齐"）。柱值本身正确（1.000）。
- 修复：图例移出坐标轴（面板 C 上方，无框）。make_figures.py 已改并重生成；放大目检柱顶平整、图例无遮挡。
- 同步：新版 fig6 以媒体替换方式更新进两个 V5.1 docx（rId50.png，像素 4320×3360 定位，替换后验证）；文档文字零改动。
- 本地 b46472f；公开仓库同步（PDF 检查零命中）。
