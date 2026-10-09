# -*- coding: utf-8 -*-
"""Build Supplementary Tables S2 (12-direction coverage matrix) + S3 (power analysis),
update Results pointers, update submission checklist."""
import time, sys
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

R = 'D:/Typing_PD_Project/reports'
RES = 'D:/Typing_PD_Project/results'

def set_song(run, size, bold=False):
    run.font.name = '宋体'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)

def add_head(doc, text):
    p = doc.add_paragraph()
    set_song(p.add_run(text), 14, True)

def add_body(doc, text, size=12):
    p = doc.add_paragraph()
    set_song(p.add_run(text), size)
    return p

def fill_table(doc, header, rows, size=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = 'Table Grid'
    for c, txt in zip(t.rows[0].cells, header):
        set_song(c.paragraphs[0].add_run(txt), size, True)
    for row in rows:
        cells = t.add_row().cells
        for c, txt in zip(cells, row):
            set_song(c.paragraphs[0].add_run(str(txt)), size)
    return t

NAME = {'mit': 'MIT', 'tappy': 'Tappy', 'typd': 'TyPD', 'oe': 'OE'}
DISPLAY = {'gold_merged2self': '临床池→自报'}
def dir_name(d):
    if d in DISPLAY: return DISPLAY[d]
    s, t = d.split('2')
    return f'{NAME[s]}→{NAME[t]}'

def f3(x): return f'{x:.3f}'
def f2(x): return f'{x:.2f}'

# ---------- S2: coverage matrix ----------
tm = pd.read_csv(f'{RES}/transfer_matrix.csv')
assert len(tm) == 12, len(tm)
doc = Document()
add_head(doc, '补充材料表 S2. 12 个成对迁移方向的覆盖矩阵（主参照 LR 与对照 LightGBM；50 个预设随机种子均值 ± 标准差）')
header = ['方向', '档位', 'n源', 'n目标', 'LR 覆盖率', 'LR PD 条件', 'LR HC 条件', 'LR 平均集合大小', 'LR 单例率',
          'LGBM 覆盖率', 'LGBM PD 条件', 'LGBM HC 条件', 'LGBM 平均集合大小', 'LGBM 单例率']
rows = []
for _, r in tm.iterrows():
    rows.append([dir_name(r['direction']), int(r['tier']), int(r['n_source']), int(r['n_target']),
                 f"{r['coverage_mean']:.3f} ± {r['coverage_std']:.3f}", f3(r['cpc_pd_mean']), f3(r['cpc_hc_mean']),
                 f2(r['mean_size_mean']), f3(r['singleton_rate_mean']),
                 f"{r['lgbm_coverage_mean']:.3f} ± {r['lgbm_coverage_std']:.3f}", f3(r['lgbm_cpc_pd_mean']),
                 f3(r['lgbm_cpc_hc_mean']), f2(r['lgbm_mean_size_mean']), f3(r['lgbm_singleton_rate_mean'])])
fill_table(doc, header, rows)
for note in [
 '注：(1) 覆盖率与类条件覆盖为 50 个预设随机种子下的均值 ± 标准差；条件覆盖分别为 PD 与 HC 受试者中的覆盖率。',
 '(2) 档位为该迁移方向的有效特征档位（源与目标数据集支持上限中的较小值）；n源 / n目标为两队列的受试者数。',
 '(3) 本表为 12 个成对方向的描述性矩阵；三个确证性方向（含临床池→自报合并方向）的正式统计检验见正文表 2。',
]:
    add_body(doc, note, 9)
p2 = f'{R}/Supplementary_Table_S2_coverage_matrix.docx'
for attempt in range(12):
    try:
        doc.save(p2); print('SAVED S2'); break
    except PermissionError:
        print('locked S2, wait...'); time.sleep(15)
else: sys.exit(2)

# ---------- S3: power analysis ----------
pn = pd.read_csv(f'{RES}/power_table.csv')
pf = pd.read_csv(f'{RES}/power_table_frozen_n.csv')
doc = Document()
add_head(doc, '补充材料表 S3. 预注册效能分析：给定真实覆盖率时，0.80 运营判定规则的结果分布（每格 50,000 次模拟）')
add_body(doc, '面板 A. 预注册计划样本量情景', 12)
hA = ['方向', '校准样本量 n', '真实覆盖率', 'Compatible 概率', 'Incompatible 概率', 'Undetermined 概率']
rowsA = [[dir_name(r['direction']), int(r['n']), f2(r['true_coverage']), f3(r['p_compatible']),
          f3(r['p_incompatible']), f3(r['p_undetermined'])] for _, r in pn.iterrows()]
fill_table(doc, hA, rowsA)
doc.add_paragraph()
add_body(doc, '面板 B. 冻结队列实际样本量情景（与正文表 1 一致）', 12)
rowsB = [[dir_name(r['direction']), int(r['n']), f2(r['true_coverage']), f3(r['p_compatible']),
          f3(r['p_incompatible']), f3(r['p_undetermined'])] for _, r in pf.iterrows()]
fill_table(doc, hA, rowsB)
for note in [
 '注：(1) 每格为 50,000 次模拟中，0.80 运营判定规则给出的标签概率（Compatible：95% 置信区间下界 ≥ 0.80；'
 'Incompatible：上界 < 0.90；其余为 Undetermined）；true_coverage 为模拟设定的真实覆盖率情景。',
 '(2) 前三行为三个确证性方向；MIT→TyPD（is_primary = 否）仅作对照展示。',
 '(3) 面板 B 与正文队列一致：在真实覆盖率 = 0.70 时，三个确证性方向均以接近 1.00 的概率被正确标记为不相容；'
 '在真实覆盖率 = 0.90 时，MIT→Tappy 与临床池→自报亦以 ≥ 0.96 的概率被正确标记为相容，Tappy→MIT 受样本量限制为 0.70。',
]:
    add_body(doc, note, 9)
p3 = f'{R}/Supplementary_Table_S3_power_analysis.docx'
for attempt in range(12):
    try:
        doc.save(p3); print('SAVED S3'); break
    except PermissionError:
        print('locked S3, wait...'); time.sleep(15)
else: sys.exit(2)

# ---------- update Results pointers ----------
PATH = f'{R}/Results(V1)_zh.docx'
d = Document(PATH)
edits = [('覆盖矩阵见补充材料。', '覆盖矩阵见补充材料表 S2。'),
         ('预注册的效能分析见补充材料。', '预注册的效能分析见补充材料表 S3。')]
for old, new in edits:
    hits = [p for p in d.paragraphs if old in p.text]
    assert len(hits) == 1, (old, len(hits))
    p = hits[0]
    p.runs[0].text = p.text.replace(old, new)
    for r in p.runs[1:]: r.text = ''
for attempt in range(12):
    try:
        d.save(PATH); print('SAVED Results pointers'); break
    except PermissionError:
        print('locked Results, wait...'); time.sleep(15)
else: sys.exit(2)

# ---------- update checklist ----------
cl = f'{R.replace("reports", "")}/提交_补充材料/_提交清单（勿上传）.txt'
t = open(cl, encoding='utf-8').read()
anchor = '- Supplementary_Table_S1_cleaning_attrition.docx'
idx = t.find(anchor)
line_end = t.find('\n', idx)
assert idx > 0 and line_end > 0
insert = ('\n- Supplementary_Table_S2_coverage_matrix.docx — 12 个成对迁移方向覆盖矩阵（LR+LGBM：覆盖、PD/HC 条件、集合大小、单例率；50 种子均值±SD），'
          '数字自 transfer_matrix.csv 程序化填入'
          '\n- Supplementary_Table_S3_power_analysis.docx — 预注册效能分析（50,000 次/格模拟；面板 A 计划样本量、面板 B 冻结队列实际样本量），'
          '对应正文稳健性节的"效能分析见补充材料"'
          '\n- ⚠️ S1 目前为英文版（建于新规之前）；S2/S3 为中文版。合并期统一语言时 S1 需翻译，S2/S3 需译英')
t = t[:line_end] + insert + t[line_end:]
open(cl, 'w', encoding='utf-8').write(t)
print('checklist updated')
