"""Inspectable visual-query clauses, without labels, translations or silent scope changes."""
from __future__ import annotations

import math
import re

from .errors import AppError, argument_error
from .semantic_contract import check_vectors

QUERY_PROTOCOL = 'agent-semantic-clauses-v1'
MAX_CLAUSES = 8

# Deliberately bounded grammar. An unparsed negation is reported rather than
# sent as an apparently affirmative embedding. Conditions are not object masks.
_NEGATION = re.compile(r'不|没有|沒(?:有)?|并非|並非|排除|而非|不要|勿|(?i:\b(?:not|no|without|excluding|except|neither|nor)\b)')
_SPLIT = re.compile(r'\s*(?:[,，;；]\s*|\s+)(?:不是|而非|并非|並非|不要|排除|(?i:not\s+|excluding\s+|without\s+))\s*')
_ZH_INLINE = re.compile(r'\s*(?:而非|不是|并非|並非)\s*')
_AMBIGUOUS = re.compile(r'不但|不仅|不僅|不是不|并非不|並非不|(?i:\bnot\s+(?:only|without|un\w+))')


def _clause(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise argument_error('检索条件须为 1–1024 字符', field)
    return value.strip()


def compile_query(value):
    """Preserve original text and expose every embedding clause to the caller."""
    text = _clause(value.get('text'), 'query')
    structured = 'include' in value or 'exclude' in value
    if structured:
        include, exclude = value.get('include'), value.get('exclude', [])
        if not isinstance(include, list) or not 1 <= len(include) <= MAX_CLAUSES:
            raise argument_error('结构查询 include 需要 1–8 项', 'include')
        if not isinstance(exclude, list) or len(exclude) > MAX_CLAUSES:
            raise argument_error('结构查询 exclude 最多 8 项', 'exclude')
        include = [_clause(v, 'include') for v in include]
        exclude = [_clause(v, 'exclude') for v in exclude]
        parser = 'explicit-clauses'
    else:
        if _AMBIGUOUS.search(text):
            raise AppError('SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW',
                '否定范围不明确；请在查询文件中显式提供 include/exclude', exit_code=2)
        parts = _SPLIT.split(text)
        if len(parts) == 1:
            parts = _ZH_INLINE.split(text)
        include, exclude = [parts[0].strip(' ,，;；')], [p.strip(' ,，;；') for p in parts[1:]]
        parser = 'bounded-negation-grammar' if exclude else 'affirmative-text'
        if exclude and re.search(r'(?i)\b(?:that|which|who|whose)\b|\b(?:is|are|was|were)\s*$', include[0]):
            raise AppError('SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW',
                '从句否定需要显式 include/exclude，不能自动改变动作或对象范围', exit_code=2)
        if not include[0] or len(exclude) > MAX_CLAUSES:
            raise argument_error('需要明确的正向主体及最多 8 个排除条件', 'query')
    if any(_NEGATION.search(v) for v in include + exclude):
        raise AppError('SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW',
            '条件仍含未解析否定；请确认范围并提供正向描述的 include/exclude', exit_code=2)
    normalized = lambda v: re.sub(r'\s+', ' ', v).casefold()
    positive = [normalized(v) for v in include]
    negative = [normalized(v) for v in exclude]
    if (len(set(positive)) != len(positive) or len(set(negative)) != len(negative)
            or set(positive) & set(negative)):
        raise argument_error('检索条件不能重复或同时包含与排除同一描述', 'query')
    return dict(protocol=QUERY_PROTOCOL, parser=parser, original_text=value['text'],
                include=include, exclude=exclude,
                semantics='all positive clauses; each must outrank every exclusion on the sampled frame')


def prepare(items):
    """Deduplicate exact clause text; retain a map for every original query."""
    compiled, inputs, positions = [], [], {}
    for item in items:
        plan = compile_query(item)
        for key in ('include', 'exclude'):
            references = []
            for text in plan[key]:
                normalized = text.lower()
                if normalized not in positions:
                    positions[normalized] = len(inputs)
                    inputs.append(dict(id='clause_' + str(len(inputs)), text=text))
                references.append(positions[normalized])
            plan[key + '_rows'] = references
        compiled.append(plan)
    if len(inputs) > 1024:
        raise argument_error('一次批量查询最多 1024 个不同条件', 'queries')
    return compiled, inputs


def rank_clauses(vectors, features, records, plan, *, limit, minimum=-1., kind=None,
                 distinct_assets=True, cutoff=None):
    """All clauses share one sampled frame; exclusions are relative evidence."""
    import numpy as np
    if (type(limit) is not int or not 1 <= limit <= 100 or type(minimum) not in (int, float)
            or not math.isfinite(minimum) or not -1 <= minimum <= 1 or kind not in (None, 'image', 'video')):
        raise argument_error('检索 limit/min-score/kind 无效', 'semantic search')
    matrix = check_vectors(vectors, len(records)).astype(np.float64)
    queries = check_vectors(features, len(features)).astype(np.float64)
    positive = matrix @ queries[plan['include_rows']].T
    negative = matrix @ queries[plan['exclude_rows']].T if plan['exclude_rows'] else None
    score = positive.min(axis=1)
    eligible = np.ones(len(records), dtype=bool)
    if negative is not None:
        eligible &= score > negative.max(axis=1)
    ordered = sorted(range(len(records)), key=lambda i: (-float(score[i]), str(records[i]['asset_id']),
                                                        records[i]['sample_seconds'], i))
    hits, seen = [], set()
    for index in ordered:
        row = records[index]
        if (not eligible[index] or (kind and row['kind'] != kind) or score[index] < minimum
                or (cutoff is not None and score[index] <= cutoff)
                or (distinct_assets and row['asset_id'] in seen)):
            continue
        seen.add(row['asset_id'])
        hit = {**row, 'row': index, 'score': round(float(score[index]), 8),
               'decision_score': float(score[index]), 'score_kind': 'minimum_clause_cosine_not_probability',
               'positive_scores': [float(v) for v in positive[index]],
               'exclusion_scores': [float(v) for v in negative[index]] if negative is not None else [],
               'review_required': True}
        hits.append(hit)
        if len(hits) == limit:
            break
    return hits
