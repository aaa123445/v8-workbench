"""中英混合分词。

为什么不用 SQLite FTS5 自带的分词器：unicode61 把整句连续中文当成单个 token，
检索"组织同步"根本无法命中"三方到V8组织同步基本逻辑"。而 2.1MB 语料量下，
自建 bigram 倒排的构建成本只有几十毫秒，召回质量却高出一个量级。

策略：
  CJK 字符 -> 相邻二元组（bigram）+ 单字（低权重兜底）
  ASCII/数字 -> 小写单词
  保留少量长度 >=2 的英文缩写（如 UDC、BPM、SPI）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CJK = r"一-鿿㐀-䶿"
_ASCII_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9_.\-]*")
_CJK_RUN = re.compile(f"[{_CJK}]+")
_ASCII_RUN = re.compile(r"[0-9a-zA-Z]+")

# 中文停用字：单字索引里噪音很大
_CJK_STOP = set("的了和是在有与及或等这那你我他它们个就都而及其之为以于对把被从到把")

# 技术缩写必须整体保留，否则 "udc" 会被切成 u/d/c
_KEEP_TOKEN = {
    "udc", "bpm", "spi", "sdk", "api", "mq", "es", "jvm", "sql",
    "nacos", "dubbo", "mybatis", "swagger", "rest", "jssdk", "mf",
    "v5", "v8", "cap", "cip", "cmp", "oa", "sso", "ocr", "gis",
}


@dataclass(frozen=True)
class Token:
    text: str
    weight: float
    is_cjk: bool


def tokenize(text: str) -> list[Token]:
    """返回带权重的 token 序列（保留重复，位置信息由调用方按需使用）。"""
    if not text:
        return []
    out: list[Token] = []

    # 先把 ASCII 词抽出来做整体匹配，同时把 CJK 段落按顺序处理
    for run in _CJK_RUN.finditer(text):
        seg = run.group(0)
        if len(seg) == 1:
            if seg not in _CJK_STOP:
                out.append(Token(seg, 0.3, True))
            continue
        # bigram 是主力
        for i in range(len(seg) - 1):
            bg = seg[i : i + 2]
            if bg[0] in _CJK_STOP and bg[1] in _CJK_STOP:
                continue
            out.append(Token(bg, 1.0, True))
        # 单字兜底，权重压低，避免"的"类高频字污染
        if len(seg) <= 6:
            for ch in seg:
                if ch not in _CJK_STOP:
                    out.append(Token(ch, 0.2, True))

    for m in _ASCII_RUN.finditer(text):
        w = m.group(0).lower()
        if not w:
            continue
        if w in _KEEP_TOKEN:
            out.append(Token(w, 1.4, False))
        elif len(w) <= 1:
            continue
        else:
            out.append(Token(w, 1.0, False))
        # 驼峰/下划线拆分出的子词也进索引，提升 SeeyonSpringBoot -> spring 的可检索性
        for sub in re.split(r"[_.\-]", m.group(0)):
            s = sub.lower()
            if len(s) >= 3 and s != w and s not in _KEEP_TOKEN:
                out.append(Token(s, 0.6, False))

    return out


def token_texts(text: str) -> list[str]:
    """轻量版本：只要 token 字符串，用于构建倒排表。"""
    return [t.text for t in tokenize(text)]


def query_terms(query: str) -> dict[str, float]:
    """查询侧聚合：同一个 token 只保留最高权重，避免长查询被重复词主导。"""
    terms: dict[str, float] = {}
    for t in tokenize(query):
        if t.text not in terms or terms[t.text] < t.weight:
            terms[t.text] = t.weight
    # 查询词越多，单 term 权重越低，防止长 query 虚高
    n = max(1, len(terms))
    damp = 1.0 / (1.0 + 0.02 * max(0, n - 8))
    return {k: v * damp for k, v in terms.items()}
