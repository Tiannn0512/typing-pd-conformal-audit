# DATA_MANIFEST.md — 四库原始数据清单（TODO-0.2）

**生成**：2026-09-25 20:52 ｜ **状态**：四库全部落盘并验证 ✅ ｜ **总体积**：~214MB
**下载通道记录**：直连跨境实测 3.7–31KB/s（晚间），切换本机代理 `http://127.0.0.1:10808` 后 250–445KB/s（**约 13 倍提速**，用户代理开启为前提——后续任何再下载优先走此通道）；MIT 为直连 3 并发完成（总量小）。
**验收口径**：研究计划书 v1.3.2 §4.6 + TODO-0.2 Golden gate +《research-playbook》内容指纹验收（条目数/字节数/官方哈希三对账）。

---

## 1. Tappy Keystroke（PhysioNet tappy 1.0.0）

| 项 | 值 |
|---|---|
| 文件 | `data/raw/tappy/Archived-Data.zip`（89,176,393 B）+ `Archived-users.zip`（73,032 B）+ `SHA256SUMS.txt`（官方）+ `Archived-users-extracted/`（227 个用户标签 txt，2026-09-25 16:21 前解压） |
| 官方 SHA256 对拍 | Archived-Data.zip = `d5fb550625211deed5a712705316bb4c79593d752f8403d9dc25e58c8230e580` ✅ 与官方 SHA256SUMS.txt 一致；Archived-users.zip = `a15f5eeac9004aaba0aa3c31b81d791256b6012bc8ae64f6fc556cd607df77fd` ✅ 一致 |
| 内容指纹 | 标签表 227 人 ✅（=可行性报告预期 227：PD 169/HC 55/单纯震颤 3）；事件 zip 字节级哈希验证通过 |
| 时间戳 | Archived-Data.zip：2026-09-25 16:21 直连至 47% → 20:44 代理续传 → 20:45 完成；users.zip：20:46 |
| 预期内容 | 227 人 × 月文件 txt（Tab 分隔，Hand/HoldTime/Direction/LatencyTime/FlightTime），Phase 1 解压解析 |

## 2. MIT-CSXPD（PhysioNet nqmitcsxpd 1.0.0）

| 项 | 值 |
|---|---|
| 文件 | `data/raw/mit/`：MIT-CS1PD/ + MIT-CS2PD/（逐 session CSV）+ 两库 `GT_DataPD_*.csv` + 官方 `SHA256SUMS.txt` + `neuroQWERTY.zip` + `nqDataLoader.py` + `readme.ipynb`，共 **122 个文件**（对账 `_keys.txt` 122/122，零缺件零空文件） |
| 官方 SHA256 对拍 | **121/121 全部 OK**（`sha256sum -c`，SUMS 不含自身） |
| Golden gate | `GT_DataPD_MIT-CS1PD.csv` = **3,248 B** ✅（TODO-0.2 锚点精确命中；GT_CS2PD = 4,181 B） |
| 体积/时间戳 | 7.6MB ｜ 2026-09-25 20:38–20:44（直连 3 并发） |
| 预期内容 | 85 人（42 PD/43 HC）临床金标准；Phase 1 与 nqDataLoader 对拍 |

## 3. TyPD / i-PROGNOSIS DS2.5（Zenodo record 2571623）

| 项 | 值 |
|---|---|
| 文件 | `data/raw/typd/typd.zip`（365,931 B，zip 结构有效 ✅） |
| SHA256（官方哈希对账通过） | 本地 SHA256 = `b5096d30c425edba8b87e320caed8f78dcabc496f9f1a4bc374a5ba14c8ada2f`；Zenodo API 官方 md5 = `54be254f9194789102ab4e279cff2182`，与本地重算一致（2026-09-25 审核复核）；官方 size = 365,931 B 一致 |
| 内容指纹 | 体积 365,931B ✅（可行性报告实测 365 kB）；官方哈希级对账通过 ✅ |
| 时间戳 | 2026-09-25 20:38（zenodo IP 直连 `--resolve zenodo.org:443:188.185.43.153` 绕 DNS 污染） |
| 预期内容 | 33 人（18 PD/15 HC）金标准 + UPDRS-III/H-Y/LEDD Excel；Phase 1 解压核数 |

## 4. Online English（OSF ew34b，CoNLL 2020）

| 项 | 值 |
|---|---|
| 文件 | `data/raw/oe/CoNLL_2020_Online_English.csv`（**125,426,343 B**） |
| Golden gate | 字节数 = **125,426,343 B ✅（TODO-0.2 锚点一字节不差）** |
| SHA256（官方哈希对账通过） | 本地 SHA256 = `db2166b5211b359c0bea4fb3057d8a41fecfbc98057fdc23c2f8fbe946984403` = **OSF API 官方 SHA256（逐位一致）**；本地 MD5 `881d7e7ba2ceb8e7ca5fc5e5eb97946a` = OSF 官方 MD5（2026-09-25 审核复核） |
| 时间戳 | 2026-09-25 20:38 直连起（~3.4MB）→ 20:45 代理续传 → 20:49 完成（实测峰值 ~445KB/s） |
| 预期内容 | 230 人（100 PD/130 HC）自报；9 列 schema；Phase 1 chunksize 分块解析 |

---

## 验收结论

- **Golden gate（TODO-0.2）**：四库齐全 ✅；Tappy SHA256 对上官方 ✅；MIT GT = 3,248B ✅；OE = 125,426,343B ✅。
- **内容指纹（playbook U04）**：条目数（122/227/365931B/125426343B）与官方或可行性报告预期全部对上；**四库全部达成官方哈希级对账**（Tappy/MIT 官方 SHA256SUMS 全量通过；TyPD 经 Zenodo API 官方 md5、OE 经 OSF API 官方 SHA256+MD5 复核通过），另留本地哈希备查。
- **红线遵守**：Tappy 47% 断点经 `-C -` 续传保住，未覆盖；原始数据不入 git（.gitignore `data/`），本清单为唯一入库凭证。
- **Phase 0 里程碑条件达成**：四库落盘锁定。
