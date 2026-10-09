#!/usr/bin/env python
"""crosscheck_mit_official.py — 本解析器 vs 官方 nqDataLoader 逐文件对拍（TODO-1.1 gate）

对拍原则：官方模块原码原样执行（sanityCheck / filtData 内部逻辑零改动），
仅做两处 Python3 兼容 shim（不改语义）：
  ① 官方代码是 Python2：print 语句只存在于 debug 分支，本对拍不触发；
  ② genfromtxt(dtype=None) 在 py3 下 f0 是 bytes，官方 filtData 的 str 正则会 TypeError——
     对拍 shim 在加载后把 keys 转为 str（与官方 py2 行为等价），再按官方顺序
     sanityCheck → filtData(FLT_NO_MOUSE|FLT_NO_LONG_META) 执行。

对比量：每文件官方保留事件数 vs 本解析器（parse_mit.py）保留事件数。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "raw" / "mit"))

import re
import types

_nq_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "mit" / "nqDataLoader.py"
# 官方文件是 Python2 源码，三处 py3 兼容 shim（均不改语义）：
# ① tab/空格混用：py2 分词器按 tab stop=8 折算，expandtabs(8) 精确复现；
# ② py2 print 语句（仅 debug 分支使用）：中和为 pass 以通过 py3 编译，执行路径不触发；
# ③ genfromtxt 在 py3 下 f0 为 bytes：shim 类加载后转 str，官方 filtData 正则才能工作。
_src = _nq_path.read_text(encoding="utf-8").expandtabs(8)
_src = re.sub(r"^(\s*)print\s+(?!\().*$", r"\1pass  # py2 print (shimmed)", _src, flags=re.M)
nq = types.ModuleType("nqDataLoader_official")
exec(compile(_src, str(_nq_path), "exec"), nq.__dict__)


class Py3ShimLoader(nq.NqDataLoader):
    """官方 loadDataFile 的 py3 shim：加载(autoFilt=False) → keys 转str → 官方 sanityCheck → 官方 filtData。"""

    def load_and_filter(self, file_in):
        res = self.loadDataFile(file_in, False, None)  # 官方加载 + 官方 sanityCheck（内部执行）
        if res is not True:
            raise RuntimeError(f"官方 loader 加载失败: {file_in}")
        self.dataKeys = np.array([k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in self.dataKeys])
        self.filtData(self.FLT_NO_MOUSE | self.FLT_NO_LONG_META)  # 官方 autoFilt=True 的默认 flag
        return len(self.dataKeys)


def main() -> None:
    report = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "interim" / "parse_reports" / "parse_mit_report.json").read_text()
    )
    mine = {r["file"]: r["n_kept"] for r in report["per_file"]}

    raw = Path(__file__).resolve().parents[1] / "data" / "raw" / "mit"
    files = sorted((raw / "MIT-CS1PD" / "data_MIT-CS1PD").glob("*.csv")) + sorted(
        (raw / "MIT-CS2PD" / "data_MIT-CS2PD").glob("*.csv")
    )

    diffs = []
    for p in files:
        loader = Py3ShimLoader()
        official_n = loader.load_and_filter(str(p))
        my_n = mine.get(p.name)
        if official_n != my_n:
            diffs.append((p.name, official_n, my_n))

    print(f"[crosscheck] files={len(files)} mismatches={len(diffs)}")
    if diffs:
        for name, o, m in diffs[:20]:
            print(f"  DIFF {name}: official={o} mine={m}")
        sys.exit(1)
    total_official = 0
    print("[crosscheck] ALL MATCH — 每文件保留事件数与官方 nqDataLoader 完全一致")


if __name__ == "__main__":
    main()
