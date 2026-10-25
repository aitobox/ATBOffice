"""Modern Dynamic Array and lookup/reference worksheet functions for Ledger."""

from __future__ import annotations

import math
import random
import re
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import (
    compare_excel_values,
    to_bool,
    to_num,
    to_str,
)
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    CALC,
    NA,
    NUM,
    REF,
    VALUE,
    ExcelError,
    is_error,
)

# Central dictionary of dynamic array functions to be registered
DYNAMIC_FUNCTIONS: dict[str, Any] = {}


def register_dynamic(name: str) -> Any:
    def decorator(fn: Any) -> Any:
        DYNAMIC_FUNCTIONS[name.upper()] = fn
        return fn

    return decorator


def to_arr(val: Any, ctx: EvalContext | None = None) -> Arr:
    if isinstance(val, Arr):
        return val
    if isinstance(val, Ref):
        return val.to_array()
    if isinstance(val, (list, tuple)):
        if val and isinstance(val[0], (list, tuple)):
            return Arr([[item for item in row] for row in val])
        return Arr([[item] for item in val])
    return Arr([[val]])


def excel_sort_key(val: Any) -> tuple[int, Any]:
    if val is None or val == "":
        return (4, 0)
    if is_error(val):
        return (3, str(val))
    if isinstance(val, bool):
        return (2, 1 if val else 0)
    if isinstance(val, (int, float)):
        return (0, float(val))
    if isinstance(val, str):
        return (1, val.lower())
    return (4, 0)


@register_dynamic("SEQUENCE")
def fn_sequence(
    rows: Any,
    columns: Any = 1,
    start: Any = 1,
    step: Any = 1,
    ctx: EvalContext | None = None,
) -> Any:
    nr = to_num(rows, ctx)
    nc = to_num(columns, ctx)
    ns = to_num(start, ctx)
    nst = to_num(step, ctx)
    if is_error(nr) or is_error(nc) or is_error(ns) or is_error(nst):
        return VALUE
    r = int(nr)
    c = int(nc)
    s = float(ns)
    st = float(nst)
    if r < 1 or c < 1:
        return VALUE
    data = []
    val = s
    for _ in range(r):
        row = []
        for _ in range(c):
            row.append(int(val) if val.is_integer() else val)
            val += st
        data.append(row)
    return Arr(data)


@register_dynamic("RANDARRAY")
def fn_randarray(
    rows: Any = 1,
    columns: Any = 1,
    min_val: Any = 0,
    max_val: Any = 1,
    whole_number: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    r = int(to_num(rows, ctx) or 1)
    c = int(to_num(columns, ctx) or 1)
    mn = float(to_num(min_val, ctx) if min_val is not None else 0)
    mx = float(to_num(max_val, ctx) if max_val is not None else 1)
    whole = bool(to_bool(whole_number))
    if r < 1 or c < 1 or mn > mx:
        return VALUE
    data = []
    for _ in range(r):
        row = []
        for _ in range(c):
            if whole:
                row.append(random.randint(int(mn), int(mx)))
            else:
                row.append(random.uniform(mn, mx))
        data.append(row)
    return Arr(data)


@register_dynamic("FILTER")
def fn_filter(
    array: Any, include: Any, if_empty: Any = None, ctx: EvalContext | None = None
) -> Any:
    A = to_arr(array, ctx)
    I = to_arr(include, ctx)
    if I.cols == 1 and I.rows == A.rows:
        keep = [to_bool(I.data[r][0]) for r in range(I.rows)]
        out = [A.data[r] for r in range(A.rows) if keep[r] is True]
    elif I.rows == 1 and I.cols == A.cols:
        keep = [to_bool(I.data[0][c]) for c in range(I.cols)]
        out = [[row[c] for c in range(A.cols) if keep[c] is True] for row in A.data]
    else:
        return VALUE
    if not out or not out[0]:
        return CALC if if_empty is None else if_empty
    return Arr(out)


@register_dynamic("UNIQUE")
def fn_unique(
    array: Any,
    by_col: Any = False,
    exactly_once: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    A = to_arr(array, ctx)
    by_col_b = bool(to_bool(by_col))
    once_b = bool(to_bool(exactly_once))

    items = (
        [[A.data[r][c] for r in range(A.rows)] for c in range(A.cols)]
        if by_col_b
        else A.data
    )

    def row_key(row: list[Any]) -> tuple[Any, ...]:
        return tuple(
            str(x).lower() if isinstance(x, str) else (type(x).__name__, x) for x in row
        )

    counts: dict[tuple[Any, ...], int] = {}
    for it in items:
        k = row_key(it)
        counts[k] = counts.get(k, 0) + 1

    seen: set[tuple[Any, ...]] = set()
    out = []
    for it in items:
        k = row_key(it)
        if once_b:
            if counts[k] == 1:
                out.append(it)
        else:
            if k not in seen:
                seen.add(k)
                out.append(it)
    if not out:
        return CALC
    if by_col_b:
        return Arr([[col[r] for col in out] for r in range(A.rows)])
    return Arr(out)


@register_dynamic("SORT")
def fn_sort(
    array: Any,
    sort_index: Any = 1,
    sort_order: Any = 1,
    by_col: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    A = to_arr(array, ctx)
    idx = int(to_num(sort_index, ctx) or 1)
    ord_val = int(to_num(sort_order, ctx) or 1)
    by_col_b = bool(to_bool(by_col))
    if ord_val not in (1, -1):
        return VALUE

    if not by_col_b:
        if idx < 1 or idx > A.cols:
            return VALUE
        rows = list(A.data)
        rows.sort(key=lambda r: excel_sort_key(r[idx - 1]), reverse=(ord_val == -1))
        return Arr(rows)
    else:
        if idx < 1 or idx > A.rows:
            return VALUE
        cols_indices = list(range(A.cols))
        cols_indices.sort(
            key=lambda c: excel_sort_key(A.data[idx - 1][c]), reverse=(ord_val == -1)
        )
        return Arr([[row[c] for c in cols_indices] for row in A.data])


@register_dynamic("SORTBY")
def fn_sortby(array: Any, *args: Any, ctx: EvalContext | None = None) -> Any:
    A = to_arr(array, ctx)
    if not args:
        return VALUE
    keys = []
    i = 0
    while i < len(args):
        k_arr = to_arr(args[i], ctx)
        order = 1
        if i + 1 < len(args) and not isinstance(args[i + 1], (Arr, Ref)):
            order = int(to_num(args[i + 1], ctx) or 1)
            i += 2
        else:
            i += 1
        if order not in (1, -1):
            return VALUE
        if k_arr.cols == 1 and k_arr.rows == A.rows:
            keys.append(([r[0] for r in k_arr.data], order, True))
        elif k_arr.rows == 1 and k_arr.cols == A.cols:
            keys.append((k_arr.data[0], order, False))
        else:
            return VALUE

    by_rows = keys[0][2]
    if any(k[2] != by_rows for k in keys):
        return VALUE

    n = A.rows if by_rows else A.cols
    order_indices = list(range(n))

    def multi_sort_key(idx: int) -> tuple[Any, ...]:
        res = []
        for k_vals, o, _ in keys:
            sk = excel_sort_key(k_vals[idx])
            res.append((sk, o))
        return tuple(res)

    # Custom comparator
    import functools

    def cmp_indices(x: int, y: int) -> int:
        for k_vals, o, _ in keys:
            kx = excel_sort_key(k_vals[x])
            ky = excel_sort_key(k_vals[y])
            if kx != ky:
                c = -1 if kx < ky else 1
                return c * o
        return x - y

    order_indices.sort(key=functools.cmp_to_key(cmp_indices))
    if by_rows:
        return Arr([A.data[i] for i in order_indices])
    return Arr([[row[j] for j in order_indices] for row in A.data])


@register_dynamic("XLOOKUP")
def fn_xlookup(
    lookup_value: Any,
    lookup_array: Any,
    return_array: Any,
    if_not_found: Any = None,
    match_mode: Any = 0,
    search_mode: Any = 1,
    ctx: EvalContext | None = None,
) -> Any:
    L = to_arr(lookup_array, ctx)
    R = to_arr(return_array, ctx)
    mm = int(to_num(match_mode, ctx) or 0)
    sm = int(to_num(search_mode, ctx) or 1)

    lookup_items = L.to_flat_list()
    n = len(lookup_items)
    indices = list(range(n))
    if sm == -1:
        indices.reverse()

    found_idx = -1
    for i in indices:
        item = lookup_items[i]
        if mm == 0:
            if compare_excel_values(item, lookup_value) == 0:
                found_idx = i
                break
        elif mm == 2 and isinstance(lookup_value, str) and isinstance(item, str):
            pat = (
                "^"
                + re.escape(lookup_value).replace(r"\*", ".*").replace(r"\?", ".")
                + "$"
            )
            if re.match(pat, item, re.IGNORECASE):
                found_idx = i
                break
        elif mm in (-1, 1):
            if compare_excel_values(item, lookup_value) == 0:
                found_idx = i
                break

    if found_idx == -1 and mm in (-1, 1):
        candidates = []
        for i, item in enumerate(lookup_items):
            cmp = compare_excel_values(item, lookup_value)
            if mm == -1 and cmp < 0:
                candidates.append((item, i))
            elif mm == 1 and cmp > 0:
                candidates.append((item, i))
        if candidates:
            candidates.sort(key=lambda x: excel_sort_key(x[0]))
            found_idx = candidates[-1][1] if mm == -1 else candidates[0][1]

    if found_idx == -1:
        return NA if if_not_found is None else if_not_found

    if R.rows == n:
        res = R.data[found_idx]
        return res[0] if len(res) == 1 else Arr([res])
    elif R.cols == n:
        res = [R.data[r][found_idx] for r in range(R.rows)]
        return res[0] if len(res) == 1 else Arr([[x] for x in res])
    elif found_idx < len(R.to_flat_list()):
        return R.to_flat_list()[found_idx]
    return NA


@register_dynamic("XMATCH")
def fn_xmatch(
    lookup_value: Any,
    lookup_array: Any,
    match_mode: Any = 0,
    search_mode: Any = 1,
    ctx: EvalContext | None = None,
) -> Any:
    L = to_arr(lookup_array, ctx)
    n = len(L.to_flat_list())
    target = Arr([[i + 1] for i in range(n)])
    res = fn_xlookup(lookup_value, lookup_array, target, NA, match_mode, search_mode, ctx)
    return res


@register_dynamic("VSTACK")
def fn_vstack(*arrays: Any, ctx: EvalContext | None = None) -> Any:
    if not arrays:
        return VALUE
    arrs = [to_arr(a, ctx) for a in arrays]
    max_cols = max(a.cols for a in arrs)
    out = []
    for a in arrs:
        for r in a.data:
            row = list(r)
            while len(row) < max_cols:
                row.append(NA)
            out.append(row)
    return Arr(out)


@register_dynamic("HSTACK")
def fn_hstack(*arrays: Any, ctx: EvalContext | None = None) -> Any:
    if not arrays:
        return VALUE
    arrs = [to_arr(a, ctx) for a in arrays]
    max_rows = max(a.rows for a in arrs)
    out: list[list[Any]] = [[] for _ in range(max_rows)]
    for a in arrs:
        for r in range(max_rows):
            if r < a.rows:
                out[r].extend(a.data[r])
            else:
                out[r].extend([NA] * a.cols)
    return Arr(out)


@register_dynamic("TOCOL")
def fn_tocol(
    array: Any,
    ignore: Any = 0,
    scan_by_column: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    A = to_arr(array, ctx)
    ig = int(to_num(ignore, ctx) or 0)
    by_col = bool(to_bool(scan_by_column))
    raw = []
    if by_col:
        for c in range(A.cols):
            for r in range(A.rows):
                raw.append(A.data[r][c])
    else:
        for r in range(A.rows):
            for c in range(A.cols):
                raw.append(A.data[r][c])

    out = []
    for v in raw:
        if ig in (1, 3) and (v is None or v == ""):
            continue
        if ig in (2, 3) and is_error(v):
            continue
        out.append([v])
    if not out:
        return CALC
    return Arr(out)


@register_dynamic("TOROW")
def fn_torow(
    array: Any,
    ignore: Any = 0,
    scan_by_column: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    col = fn_tocol(array, ignore, scan_by_column, ctx)
    if is_error(col):
        return col
    return Arr([[row[0] for row in col.data]])


@register_dynamic("WRAPROWS")
def fn_wraprows(
    vector: Any, wrap_count: Any, pad_with: Any = NA, ctx: EvalContext | None = None
) -> Any:
    A = to_arr(vector, ctx)
    if A.rows != 1 and A.cols != 1:
        return VALUE
    n = int(to_num(wrap_count, ctx) or 0)
    if n < 1:
        return NUM
    flat = A.to_flat_list()
    out = []
    for i in range(0, len(flat), n):
        chunk = flat[i : i + n]
        while len(chunk) < n:
            chunk.append(pad_with)
        out.append(chunk)
    return Arr(out)


@register_dynamic("WRAPCOLS")
def fn_wrapcols(
    vector: Any, wrap_count: Any, pad_with: Any = NA, ctx: EvalContext | None = None
) -> Any:
    A = to_arr(vector, ctx)
    if A.rows != 1 and A.cols != 1:
        return VALUE
    n = int(to_num(wrap_count, ctx) or 0)
    if n < 1:
        return NUM
    flat = A.to_flat_list()
    num_cols = math.ceil(len(flat) / n)
    out: list[list[Any]] = [[] for _ in range(n)]
    for j in range(num_cols):
        for i in range(n):
            idx = j * n + i
            out[i].append(flat[idx] if idx < len(flat) else pad_with)
    return Arr(out)


@register_dynamic("TAKE")
def fn_take(
    array: Any, rows: Any = None, columns: Any = None, ctx: EvalContext | None = None
) -> Any:
    A = to_arr(array, ctx)
    r = A.rows if rows is None else int(to_num(rows, ctx) or A.rows)
    c = A.cols if columns is None else int(to_num(columns, ctx) or A.cols)
    if r == 0 or c == 0:
        return CALC
    selected_rows = A.data[:r] if r > 0 else A.data[max(0, A.rows + r) :]
    out = [
        row[:c] if c > 0 else row[max(0, A.cols + c) :] for row in selected_rows
    ]
    return Arr(out)


@register_dynamic("DROP")
def fn_drop(
    array: Any, rows: Any = 0, columns: Any = 0, ctx: EvalContext | None = None
) -> Any:
    A = to_arr(array, ctx)
    r = 0 if rows is None else int(to_num(rows, ctx) or 0)
    c = 0 if columns is None else int(to_num(columns, ctx) or 0)
    selected_rows = A.data[r:] if r >= 0 else A.data[: A.rows + r]
    out = [row[c:] if c >= 0 else row[: A.cols + c] for row in selected_rows]
    if not out or not out[0]:
        return CALC
    return Arr(out)


@register_dynamic("CHOOSEROWS")
def fn_chooserows(array: Any, *row_nums: Any, ctx: EvalContext | None = None) -> Any:
    A = to_arr(array, ctx)
    out = []
    for r in row_nums:
        idx = int(to_num(r, ctx) or 0)
        if idx == 0 or abs(idx) > A.rows:
            return VALUE
        out.append(A.data[idx - 1 if idx > 0 else A.rows + idx])
    return Arr(out)


@register_dynamic("CHOOSECOLS")
def fn_choosecols(array: Any, *col_nums: Any, ctx: EvalContext | None = None) -> Any:
    A = to_arr(array, ctx)
    cols = []
    for c in col_nums:
        idx = int(to_num(c, ctx) or 0)
        if idx == 0 or abs(idx) > A.cols:
            return VALUE
        cols.append(idx - 1 if idx > 0 else A.cols + idx)
    return Arr([[row[c] for c in cols] for row in A.data])


@register_dynamic("EXPAND")
def fn_expand(
    array: Any,
    rows: Any = None,
    columns: Any = None,
    pad_with: Any = NA,
    ctx: EvalContext | None = None,
) -> Any:
    A = to_arr(array, ctx)
    r = A.rows if rows is None else int(to_num(rows, ctx) or A.rows)
    c = A.cols if columns is None else int(to_num(columns, ctx) or A.cols)
    if r < A.rows or c < A.cols:
        return VALUE
    out = []
    for i in range(r):
        row = []
        for j in range(c):
            if i < A.rows and j < A.cols:
                row.append(A.data[i][j])
            else:
                row.append(pad_with)
        out.append(row)
    return Arr(out)


@register_dynamic("ARRAYTOTEXT")
def fn_arraytotext(array: Any, format_type: Any = 0, ctx: EvalContext | None = None) -> str:
    A = to_arr(array, ctx)
    fmt = int(to_num(format_type, ctx) or 0)
    if fmt == 0:
        return ", ".join(to_str(x) for x in A.to_flat_list())
    else:
        rows_str = [", ".join(to_str(x) for x in row) for row in A.data]
        return "{" + "; ".join(rows_str) + "}"


@register_dynamic("VALUETOTEXT")
def fn_valuetotext(value: Any, format_type: Any = 0, ctx: EvalContext | None = None) -> str:
    return fn_arraytotext(value, format_type, ctx)


@register_dynamic("TEXTSPLIT")
def fn_textsplit(
    text: Any,
    col_delimiter: Any,
    row_delimiter: Any = None,
    ignore_empty: Any = False,
    match_mode: Any = 0,
    pad_with: Any = NA,
    ctx: EvalContext | None = None,
) -> Any:
    s = to_str(text)
    cdelims = [to_str(d) for d in (col_delimiter if isinstance(col_delimiter, (list, tuple)) else [col_delimiter])]
    rdelims = [to_str(d) for d in (row_delimiter if isinstance(row_delimiter, (list, tuple)) else [row_delimiter])] if row_delimiter is not None else []
    ig = bool(to_bool(ignore_empty))

    # Split rows
    if rdelims:
        rpat = "|".join(re.escape(d) for d in rdelims)
        rows_raw = re.split(rpat, s)
    else:
        rows_raw = [s]

    cpat = "|".join(re.escape(d) for d in cdelims)
    grid = []
    for r in rows_raw:
        cols = re.split(cpat, r)
        if ig:
            cols = [c for c in cols if c != ""]
        if cols or not ig:
            grid.append(cols)

    if not grid or not any(grid):
        return CALC

    max_c = max(len(r) for r in grid)
    out = []
    for r in grid:
        row = list(r)
        while len(row) < max_c:
            row.append(pad_with)
        out.append(row)
    return Arr(out)


@register_dynamic("TEXTBEFORE")
def fn_textbefore(
    text: Any,
    delimiter: Any,
    instance_num: Any = 1,
    match_mode: Any = 0,
    match_end: Any = 0,
    if_not_found: Any = NA,
    ctx: EvalContext | None = None,
) -> Any:
    s = to_str(text)
    d = to_str(delimiter)
    inst = int(to_num(instance_num, ctx) or 1)
    flags = re.IGNORECASE if match_mode == 1 else 0
    matches = [m.start() for m in re.finditer(re.escape(d), s, flags=flags)]
    if not matches:
        return s if match_end == 1 else if_not_found
    if inst > 0:
        if inst > len(matches):
            return s if match_end == 1 else if_not_found
        return s[: matches[inst - 1]]
    else:
        if abs(inst) > len(matches):
            return "" if match_end == 1 else if_not_found
        return s[: matches[len(matches) + inst]]


@register_dynamic("TEXTAFTER")
def fn_textafter(
    text: Any,
    delimiter: Any,
    instance_num: Any = 1,
    match_mode: Any = 0,
    match_end: Any = 0,
    if_not_found: Any = NA,
    ctx: EvalContext | None = None,
) -> Any:
    s = to_str(text)
    d = to_str(delimiter)
    inst = int(to_num(instance_num, ctx) or 1)
    flags = re.IGNORECASE if match_mode == 1 else 0
    matches = list(re.finditer(re.escape(d), s, flags=flags))
    if not matches:
        return "" if match_end == 1 else if_not_found
    if inst > 0:
        if inst > len(matches):
            return "" if match_end == 1 else if_not_found
        return s[matches[inst - 1].end() :]
    else:
        if abs(inst) > len(matches):
            return s if match_end == 1 else if_not_found
        return s[matches[len(matches) + inst].end() :]


@register_dynamic("TRANSPOSE")
def fn_transpose(array: Any, ctx: EvalContext | None = None) -> Any:
    A = to_arr(array, ctx)
    out = [[A.data[r][c] for r in range(A.rows)] for c in range(A.cols)]
    return Arr(out)


@register_dynamic("ROWS")
def fn_rows(array: Any, ctx: EvalContext | None = None) -> int:
    if isinstance(array, Ref):
        return array.rows
    if isinstance(array, Arr):
        return array.rows
    return 1


@register_dynamic("COLUMNS")
def fn_columns(array: Any, ctx: EvalContext | None = None) -> int:
    if isinstance(array, Ref):
        return array.cols
    if isinstance(array, Arr):
        return array.cols
    return 1


@register_dynamic("ROW")
def fn_row(ref: Any = None, ctx: EvalContext | None = None) -> int:
    if ref is None and ctx is not None:
        return ctx.current_row + 1
    if isinstance(ref, Ref):
        return ref.r1 + 1
    return 1


@register_dynamic("COLUMN")
def fn_column(ref: Any = None, ctx: EvalContext | None = None) -> int:
    if ref is None and ctx is not None:
        return ctx.current_col + 1
    if isinstance(ref, Ref):
        return ref.c1 + 1
    return 1


@register_dynamic("AREAS")
def fn_areas(ref: Any, ctx: EvalContext | None = None) -> int:
    return 1


@register_dynamic("ADDRESS")
def fn_address(
    row_num: Any,
    column_num: Any,
    abs_num: Any = 1,
    a1: Any = True,
    sheet_text: Any = None,
    ctx: EvalContext | None = None,
) -> str:
    r = int(to_num(row_num, ctx) or 1)
    c = int(to_num(column_num, ctx) or 1)
    abs_mode = int(to_num(abs_num, ctx) or 1)
    is_a1 = bool(to_bool(a1))

    # Convert column number to letter
    def col_to_letter(col: int) -> str:
        res = ""
        while col > 0:
            col, rem = divmod(col - 1, 26)
            res = chr(65 + rem) + res
        return res

    if is_a1:
        col_str = col_to_letter(c)
        if abs_mode == 1:
            cell = f"${col_str}${r}"
        elif abs_mode == 2:
            cell = f"{col_str}${r}"
        elif abs_mode == 3:
            cell = f"${col_str}{r}"
        else:
            cell = f"{col_str}{r}"
    else:
        if abs_mode == 1:
            cell = f"R{r}C{c}"
        elif abs_mode == 2:
            cell = f"R{r}C[{c}]"
        elif abs_mode == 3:
            cell = f"R[{r}]C{c}"
        else:
            cell = f"R[{r}]C[{c}]"

    if sheet_text:
        st = to_str(sheet_text)
        if " " in st:
            return f"'{st}'!{cell}"
        return f"{st}!{cell}"
    return cell


@register_dynamic("OFFSET")
def fn_offset(
    reference: Any,
    rows: Any,
    cols: Any,
    height: Any = None,
    width: Any = None,
    ctx: EvalContext | None = None,
) -> Any:
    if not isinstance(reference, Ref) or ctx is None:
        return VALUE
    dr = int(to_num(rows, ctx) or 0)
    dc = int(to_num(cols, ctx) or 0)
    h = reference.rows if height is None else int(to_num(height, ctx) or reference.rows)
    w = reference.cols if width is None else int(to_num(width, ctx) or reference.cols)
    if h < 1 or w < 1:
        return VALUE
    r1 = reference.r1 + dr
    c1 = reference.c1 + dc
    r2 = r1 + h - 1
    c2 = c1 + w - 1
    if r1 < 0 or c1 < 0:
        return REF
    return ctx.create_ref(reference.sheet, r1, c1, r2, c2)


@register_dynamic("INDIRECT")
def fn_indirect(ref_text: Any, a1: Any = True, ctx: EvalContext | None = None) -> Any:
    if ctx is None:
        return REF
    s = to_str(ref_text).strip()
    sheet = ctx.current_sheet
    if "!" in s:
        sheet_part, s = s.split("!", 1)
        sheet = sheet_part.strip("'\"")

    from atboffice.modules.spreadsheet.calc.references import parse_cell_reference

    parsed = parse_cell_reference(s)
    if parsed is not None:
        r1, c1, r2, c2 = parsed
        return ctx.create_ref(sheet, r1, c1, r2, c2)
    return REF


@register_dynamic("FORMULATEXT")
def fn_formulatext(reference: Any, ctx: EvalContext | None = None) -> Any:
    if not isinstance(reference, Ref) or ctx is None:
        return NA
    val = ctx.get_cell_value(reference.sheet, reference.r1, reference.c1)
    if isinstance(val, str) and val.startswith("="):
        return val
    return NA


@register_dynamic("SINGLE")
def fn_single(val: Any, ctx: EvalContext | None = None) -> Any:
    if isinstance(val, Arr):
        return val.get(0, 0)
    if isinstance(val, Ref):
        return val.cell_value(val.r1, val.c1)
    return val


@register_dynamic("ANCHORARRAY")
def fn_anchorarray(reference: Any, ctx: EvalContext | None = None) -> Any:
    return reference


@register_dynamic("TEXTJOIN")
def fn_textjoin(
    delimiter: Any,
    ignore_empty: Any,
    *args: Any,
    ctx: EvalContext | None = None,
) -> Any:
    delim_str = to_str(delimiter)
    ign = to_bool(ignore_empty)
    if is_error(ign):
        return ign

    collected: list[str] = []
    for arg in args:
        if isinstance(arg, (Arr, Ref)):
            arr_val = to_arr(arg, ctx)
            for item in arr_val.to_flat_list():
                if is_error(item):
                    return item
                if item is None or item == "":
                    if not ign:
                        collected.append("")
                else:
                    collected.append(to_str(item))
        else:
            if is_error(arg):
                return arg
            if arg is None or arg == "":
                if not ign:
                    collected.append("")
            else:
                collected.append(to_str(arg))

    return delim_str.join(collected)


@register_dynamic("MAP")
def fn_map(*args: Any, ctx: EvalContext | None = None) -> Any:
    if len(args) < 2:
        return VALUE
    fn = args[-1]
    if not callable(fn):
        return VALUE
    arrays = [to_arr(a, ctx) for a in args[:-1]]
    rows = arrays[0].rows
    cols = arrays[0].cols
    for a in arrays[1:]:
        if a.rows != rows or a.cols != cols:
            return VALUE

    out_matrix: list[list[Any]] = []
    for r in range(rows):
        out_row: list[Any] = []
        for c in range(cols):
            call_items = [a.get(r, c) for a in arrays]
            res = fn(*call_items, ctx=ctx)
            if is_error(res):
                return res
            out_row.append(res)
        out_matrix.append(out_row)

    return Arr(out_matrix)


@register_dynamic("REDUCE")
def fn_reduce(
    initial_value: Any,
    array: Any,
    lambda_fn: Any,
    ctx: EvalContext | None = None,
) -> Any:
    if not callable(lambda_fn):
        return VALUE
    arr = to_arr(array, ctx)
    acc = initial_value
    for item in arr.to_flat_list():
        acc = lambda_fn(acc, item, ctx=ctx)
        if is_error(acc):
            return acc
    return acc


@register_dynamic("BYROW")
def fn_byrow(array: Any, lambda_fn: Any, ctx: EvalContext | None = None) -> Any:
    if not callable(lambda_fn):
        return VALUE
    arr = to_arr(array, ctx)
    out: list[list[Any]] = []
    for r in range(arr.rows):
        row_arr = Arr([arr.data[r]])
        res = lambda_fn(row_arr, ctx=ctx)
        if is_error(res):
            return res
        out.append([res])
    return Arr(out)


@register_dynamic("BYCOL")
def fn_bycol(array: Any, lambda_fn: Any, ctx: EvalContext | None = None) -> Any:
    if not callable(lambda_fn):
        return VALUE
    arr = to_arr(array, ctx)
    out_row: list[Any] = []
    for c in range(arr.cols):
        col_arr = Arr([[arr.get(r, c)] for r in range(arr.rows)])
        res = lambda_fn(col_arr, ctx=ctx)
        if is_error(res):
            return res
        out_row.append(res)
    return Arr([out_row])


@register_dynamic("LET")
def fn_let(*args: Any, ctx: EvalContext | None = None) -> Any:
    # Fallback if called directly
    return args[-1] if args else VALUE


@register_dynamic("LAMBDA")
def fn_lambda(*args: Any, ctx: EvalContext | None = None) -> Any:
    # Fallback if called directly
    return args[-1] if args else VALUE


# Placeholder external/cube/web stubs that return original cell value or #N/A
PLACEHOLDER_STUBS = [
    "GETPIVOTDATA",
    "CUBEMEMBER",
    "CUBEVALUE",
    "CUBESET",
    "CUBESETCOUNT",
    "CUBERANKEDMEMBER",
    "CUBEMEMBERPROPERTY",
    "CUBEKPIMEMBER",
    "WEBSERVICE",
    "FILTERXML",
    "RTD",
    "STOCKHISTORY",
    "CALL",
    "REGISTER.ID",
    "EUROCONVERT",
    "SQL.REQUEST",
    "IMAGE",
    "TRANSLATE",
    "DETECTLANGUAGE",
    "COPILOT",
    "PY",
]

for stub_name in PLACEHOLDER_STUBS:
    DYNAMIC_FUNCTIONS[stub_name] = lambda *args, **kwargs: NA
