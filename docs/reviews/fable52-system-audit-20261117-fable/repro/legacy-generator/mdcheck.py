"""Independent checker for the exported Markdown pattern text.

Deliberately does NOT import app.models.stitch_notation / instruction_checks /
validator: the round tables are re-read the way a maker would, by expanding the
written repeats stitch by stitch and comparing with the previous round.

Usage as a library: ``check_markdown(md_text) -> Report``.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

# ── stitch algebra (independent restatement) ────────────────────────────────
# symbol -> (source stitches consumed, new stitches produced)
OPS = {"X": (1, 1), "V": (1, 2), "A": (2, 1), "W": (1, 3), "M": (3, 1)}
_TOKEN = re.compile(r"\d+|-(?:FLO|BLO)|FLO|BLO|[XVAWM]|[(),×*+]")
MAX_OPS = 400_000


class FormulaError(ValueError):
    pass


def _tokens(text: str) -> list[str]:
    text = text.translate(str.maketrans({"（": "(", "）": ")", "，": ",", "＊": "*"}))
    out, pos = [], 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = _TOKEN.match(text, pos)
        if match is None:
            raise FormulaError(f"unrecognised text at {text[pos:pos + 12]!r}")
        out.append(match[0])
        pos = match.end()
    return out


def expand(formula: str) -> list[str]:
    """Expand a written formula into the flat, ordered list of operations."""
    tokens = _tokens(formula)
    pos = 0

    def peek() -> str:
        return tokens[pos] if pos < len(tokens) else ""

    def take() -> str:
        nonlocal pos
        pos += 1
        return tokens[pos - 1]

    def sequence() -> list[str]:
        ops = term()
        while peek() in (",", "+"):
            take()
            ops = ops + term()
        return ops

    def term() -> list[str]:
        count = int(take()) if peek().isdigit() else 1
        token = take()
        if token in ("FLO", "BLO"):
            if take() != "(":
                raise FormulaError("loop qualifier without parentheses")
            ops = sequence()
            if take() != ")":
                raise FormulaError("missing )")
        elif token == "(":
            ops = sequence()
            if take() != ")":
                raise FormulaError("missing )")
        elif token in OPS:
            ops = [token]
            if peek() in ("-FLO", "-BLO"):
                take()
        else:
            raise FormulaError(f"unexpected token {token!r}")
        ops = ops * count
        if peek() in ("×", "*"):
            take()
            if not peek().isdigit():
                raise FormulaError("repeat count missing")
            ops = ops * int(take())
        if len(ops) > MAX_OPS:
            raise FormulaError("too many operations")
        return ops

    if not tokens:
        raise FormulaError("empty")
    result = sequence()
    if pos != len(tokens):
        raise FormulaError(f"trailing tokens {tokens[pos:]}")
    return result


def tally(ops: list[str]) -> tuple[int, int, int, int]:
    consumed = sum(OPS[o][0] for o in ops)
    produced = sum(OPS[o][1] for o in ops)
    increase = sum(max(0, OPS[o][1] - OPS[o][0]) for o in ops)
    decrease = sum(max(0, OPS[o][0] - OPS[o][1]) for o in ops)
    return consumed, produced, increase, decrease


def cyclic_gaps(ops: list[str], symbol: str) -> list[int]:
    """Plain stitches between consecutive `symbol` operations, wrapping the round."""
    idx = [i for i, o in enumerate(ops) if o == symbol]
    if not idx:
        return []
    gaps = []
    for a, b in zip(idx, idx[1:] + [idx[0] + len(ops)]):
        between = [ops[k % len(ops)] for k in range(a + 1, b)]
        if any(o != "X" for o in between):
            gaps.append(-1)
        else:
            gaps.append(len(between))
    return gaps


# ── markdown parsing ───────────────────────────────────────────────────────
def _unescape(cell: str) -> str:
    cell = html.unescape(cell)
    return re.sub(r"\\([\\\[\]|])", r"\1", cell).strip()


def _split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [_unescape(c) for c in cells[1:-1]]


@dataclass
class Row:
    row: int
    stitches: int
    inc: int
    dec: int
    formula: str
    color: str
    notes: str


@dataclass
class Part:
    name: str
    quantity: int
    header_rounds: int
    bullets: dict[str, str] = field(default_factory=dict)
    magic_ring: bool = False
    notes: str = ""
    rows: list[Row] = field(default_factory=list)


@dataclass
class Pattern:
    header: list[str]
    materials: list[tuple[str, str]]
    material_summary: str
    parts: list[Part]
    assembly: list[str]
    skirt_tables: list[list[list[str]]]


_PART_HEAD = re.compile(r"^## 🧶 (.+?)(?: × (\d+) 个)? \((\d+) 圈(?:/个)?\)$")


def parse_markdown(md: str) -> Pattern:
    lines = md.split("\n")
    header, materials, parts, assembly, skirt_tables = [], [], [], [], []
    summary = ""
    section = "header"
    part: Part | None = None
    for line in lines:
        head = _PART_HEAD.match(line)
        if head:
            part = Part(_unescape(head[1]), int(head[2] or 1), int(head[3]))
            parts.append(part)
            section = "part"
            continue
        if line.startswith("## 🧵 所需材料"):
            section = "materials"
            continue
        if line.startswith("## 接裙圈序示意"):
            section = "skirt_table"
            skirt_tables.append([])
            continue
        if line.startswith("## 🔧 装配说明"):
            section = "assembly"
            continue
        if line.startswith("## "):
            raise AssertionError(f"unknown section heading: {line!r}")
        if section == "header":
            if line.startswith(">"):
                header.append(_unescape(line[1:]))
        elif section == "materials":
            m = re.match(r"^- \*\*(.+?)\*\*：(.*)$", line)
            if m:
                materials.append((_unescape(m[1]), _unescape(m[2])))
            elif line.startswith("> 毛线小计"):
                summary = _unescape(line[1:])
        elif section == "part" and part is not None:
            if line.startswith("|"):
                cells = _split_row(line)
                if cells and cells[0] not in ("圈数",) and not set(cells[0]) <= set(":-"):
                    def num(text: str) -> int:
                        text = text.strip()
                        return 0 if text in ("—", "") else int(text.lstrip("+-"))
                    part.rows.append(Row(int(cells[0]), int(cells[1]), num(cells[2]), num(cells[3]),
                                         cells[4], cells[5], cells[6]))
            elif line.startswith("- ✨ 魔法环起针"):
                part.magic_ring = True
            elif (m := re.match(r"^- \*\*(.+?)\*\*：(.*)$", line)):
                part.bullets[m[1]] = _unescape(m[2])
            elif line.startswith("> "):
                part.notes = (part.notes + " " + _unescape(line[2:])).strip()
        elif section == "skirt_table":
            if line.startswith("|"):
                cells = _split_row(line)
                if cells and cells[0] != "步骤" and not set(cells[0]) <= set(":- "):
                    skirt_tables[-1].append(cells)
        elif section == "assembly":
            if line.strip() and not line.startswith("---") and not line.startswith("*由"):
                assembly.append(_unescape(line))
    return Pattern(header, materials, summary, parts, assembly, skirt_tables)


# ── note clause interpretation (maker's reading of the 说明 column) ─────────
_NOTE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("magic_ring", re.compile(r"^魔法环起\s*(\d+)\s*针（X×(\d+)）$")),
    ("all_inc", re.compile(r"^加针×(\d+)（(V×\d+)，每针都加）$")),
    ("all_dec", re.compile(r"^减针×(\d+)（(A×\d+)，每2针并1针）$")),
    ("plain", re.compile(r"^(\d+X)（不加不减）$")),
    ("plain_start_label", re.compile(r"^(\d+X)（起针圈）$")),
    ("interval", re.compile(r"^(.+?)，隔(\d+)针([加减])1针$")),
    ("even", re.compile(r"^(.+?)，均匀([加减])(\d+)针$")),
    ("no_formula", re.compile(r"^由 (\d+) 针均匀(调整|加|减)至 (\d+) 针$")),
    ("ring_start", re.compile(r"^腰部环形起针(\d+)X成环（引拔连接，开口勿收口）$")),
    ("ruffle", re.compile(r"^波浪裙摆：每针放2针（(V×\d+)）$")),
]
_CLOSE_TIGHT = re.compile(r"穿末圈每针前半针后拉紧")
_TAIL_SEW = re.compile(r"断线留\d+(?:\.\d+)?cm用于缝合")
_KEEP_OPEN = re.compile(r"不收口|勿收口")


@dataclass
class NoteReading:
    kind: str
    formula: str | None = None
    claim: tuple | None = None
    extra: list[str] = field(default_factory=list)


def read_note(note: str) -> NoteReading:
    clauses = [c.strip() for c in note.split("；") if c.strip()]
    if not clauses:
        return NoteReading("empty")
    first, extra = clauses[0], clauses[1:]
    for kind, pattern in _NOTE_PATTERNS:
        m = pattern.match(first)
        if not m:
            continue
        if kind == "magic_ring":
            return NoteReading(kind, None, (int(m[1]), int(m[2])), extra)
        if kind in ("all_inc", "all_dec"):
            return NoteReading(kind, m[2], (int(m[1]),), extra)
        if kind in ("plain", "plain_start_label", "ruffle"):
            return NoteReading(kind, m[1], None, extra)
        if kind == "interval":
            return NoteReading(kind, m[1], (m[3], int(m[2])), extra)
        if kind == "even":
            return NoteReading(kind, m[1], (m[2], int(m[3])), extra)
        if kind == "no_formula":
            return NoteReading(kind, None, (int(m[1]), int(m[3])), extra)
        if kind == "ring_start":
            return NoteReading(kind, None, (int(m[1]),), extra)
    try:
        expand(first)
    except FormulaError:
        return NoteReading("unparsed", None, None, clauses)
    return NoteReading("bare_formula", first, None, extra)


# ── checks ─────────────────────────────────────────────────────────────────
@dataclass
class Finding:
    level: str  # ERROR / GAP / INFO
    part: str
    row: int | None
    code: str
    message: str

    def __str__(self) -> str:
        where = f"{self.part}" + (f" R{self.row}" if self.row is not None else "")
        return f"[{self.level}] {self.code} {where}: {self.message}"


@dataclass
class Report:
    pattern: Pattern
    findings: list[Finding]
    stats: dict

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "ERROR"]

    def by_code(self, code: str) -> list[Finding]:
        return [f for f in self.findings if f.code == code]


def _check_part(part: Part, out: list[Finding], stats: dict) -> None:
    add = lambda level, row, code, msg: out.append(Finding(level, part.name, row, code, msg))  # noqa: E731
    rows = part.rows
    if part.header_rounds != len(rows):
        add("ERROR", None, "ROUND_COUNT", f"heading says {part.header_rounds} rounds, table has {len(rows)}")
    if [r.row for r in rows] != list(range(1, len(rows) + 1)):
        add("ERROR", None, "ROW_NUMBERS", f"row labels are not 1..n: {[r.row for r in rows][:12]}…")
    prev: Row | None = None
    for r in rows:
        stats["rows"] += 1
        reading = read_note(r.notes)
        if prev is None:
            # ── start of the piece ──
            if reading.kind == "magic_ring":
                n_text, n_x = reading.claim
                if n_text != r.stitches or n_x != r.stitches:
                    add("ERROR", r.row, "START_COUNT", f"magic ring text {reading.claim} vs stitches {r.stitches}")
                if not part.magic_ring:
                    add("ERROR", r.row, "START_FLAG", "row 1 is a magic ring but the part lacks the 魔法环起针 bullet")
            elif reading.kind == "ring_start":
                if reading.claim[0] != r.stitches:
                    add("ERROR", r.row, "START_COUNT", f"ring start text {reading.claim[0]} vs stitches {r.stitches}")
                add("GAP", r.row, "START_RING_NO_FOUNDATION",
                    f"start is written as {r.notes!r}: no chain/foundation count or technique is given")
                if part.magic_ring:
                    add("ERROR", r.row, "START_FLAG", "ring start but part flagged magic ring")
            elif r.notes.startswith("BLO("):
                stats["attached_starts"] += 1
            else:
                add("GAP", r.row, "START_UNSPECIFIED", f"first round has no recognisable start instruction: {r.notes!r}")
            if r.inc or r.dec:
                add("ERROR", r.row, "START_DELTA", "first round declares increase/decrease")
        else:
            # ── formula column ──
            col_ops = None
            if r.formula not in ("—", ""):
                try:
                    col_ops = expand(r.formula)
                except FormulaError as exc:
                    add("GAP", r.row, "FORMULA_COL_UNREADABLE", f"{r.formula!r}: {exc}")
            note_ops = None
            if reading.formula is not None:
                try:
                    note_ops = expand(reading.formula)
                except FormulaError as exc:
                    add("GAP", r.row, "NOTE_FORMULA_UNREADABLE", f"{reading.formula!r}: {exc}")
            if reading.kind == "no_formula":
                add("GAP", r.row, "NO_EXECUTABLE_FORMULA", f"only prose: {r.notes!r}")
            if reading.kind == "unparsed":
                add("GAP", r.row, "NOTE_UNPARSED", f"{r.notes!r}")
            if reading.kind == "plain_start_label":
                add("INFO", r.row, "MISLABELLED_START", f"non-first round labelled 起针圈: {r.notes!r}")
            for label, ops in (("formula column", col_ops), ("note text", note_ops)):
                if ops is None:
                    continue
                stats["expanded"] += 1
                consumed, produced, inc, dec = tally(ops)
                if consumed != prev.stitches:
                    add("ERROR", r.row, "CONSUMES_WRONG",
                        f"{label} uses {consumed} stitches of the previous round, which has {prev.stitches}")
                if produced != r.stitches:
                    add("ERROR", r.row, "PRODUCES_WRONG",
                        f"{label} makes {produced} stitches, stated count is {r.stitches}")
                if inc != r.inc or dec != r.dec:
                    add("ERROR", r.row, "INC_DEC_COLUMNS",
                        f"{label} has +{inc}/-{dec}, columns say +{r.inc}/-{r.dec}")
            if col_ops is not None and note_ops is not None and col_ops != note_ops:
                add("ERROR", r.row, "COLUMN_NOTE_DISAGREE",
                    f"formula column {r.formula!r} and note {reading.formula!r} expand differently")
            if col_ops is None and note_ops is None and reading.kind not in ("no_formula", "unparsed"):
                add("GAP", r.row, "NO_FORMULA", f"neither column nor note carries a formula: {r.notes!r}")
            if r.stitches != prev.stitches + r.inc - r.dec:
                add("ERROR", r.row, "ALGEBRA", f"{r.stitches} != {prev.stitches} + {r.inc} - {r.dec}")
            ops = note_ops or col_ops
            if ops is not None and reading.claim is not None:
                if reading.kind == "interval":
                    direction, n = reading.claim
                    gaps = cyclic_gaps(ops, "V" if direction == "加" else "A")
                    if not gaps or any(g != n for g in gaps):
                        add("ERROR", r.row, "INTERVAL_CLAIM", f"text says 隔{n}针{direction}1针, gaps are {gaps[:8]}")
                elif reading.kind == "even":
                    direction, n = reading.claim
                    _, _, inc, dec = tally(ops)
                    if (inc if direction == "加" else dec) != n:
                        add("ERROR", r.row, "EVEN_CLAIM", f"text says 均匀{direction}{n}针, formula has +{inc}/-{dec}")
                elif reading.kind in ("all_inc", "all_dec"):
                    want = "V" if reading.kind == "all_inc" else "A"
                    if set(ops) != {want} or len(ops) != reading.claim[0]:
                        add("ERROR", r.row, "ALL_CLAIM", f"text says every stitch {want}×{reading.claim[0]}; ops {len(ops)}")
        prev = r
    # ── end of the piece ──
    if rows:
        last = rows[-1]
        if _CLOSE_TIGHT.search(last.notes):
            stats["closings"]["cinched"] += 1
            part.bullets["__finish"] = "cinched"
            if last.stitches > 12:
                add("INFO", last.row, "CINCH_WIDE", f"final round of {last.stitches} stitches is drawn closed")
        elif _TAIL_SEW.search(last.notes):
            stats["closings"]["open_tail_for_sewing"] += 1
            part.bullets["__finish"] = "open_sew"
        elif _KEEP_OPEN.search(last.notes):
            stats["closings"]["declared_open"] += 1
            part.bullets["__finish"] = "declared_open"
        else:
            stats["closings"]["none"] += 1
            part.bullets["__finish"] = "none"
            add("GAP", last.row, "NO_FINISH_INSTRUCTION",
                f"last round gives no fasten-off / close / leave-open instruction: {last.notes!r}")
        for r in rows[:-1]:
            if _CLOSE_TIGHT.search(r.notes) or _TAIL_SEW.search(r.notes):
                add("ERROR", r.row, "FINISH_NOT_LAST", f"finishing instruction before the last round: {r.notes!r}")
    # ── bullets / part notes that restate numbers ──
    by_row = {r.row: r for r in rows}
    opening = part.bullets.get("连接开口")
    if opening:
        m = re.match(r"^第 (\d+) 圈 · (\d+) 针$", opening)
        if not m or int(m[1]) not in by_row or by_row[int(m[1])].stitches != int(m[2]):
            add("ERROR", None, "OPENING_BULLET", f"连接开口 {opening!r} does not match the table")
    peak = max((r.stitches for r in rows), default=0)
    if (m := re.search(r"最大 (\d+) 针", part.notes)) and int(m[1]) != peak:
        add("ERROR", None, "NOTE_MAX", f"notes say 最大 {m[1]} 针, table peak is {peak}")
    for m in re.finditer(r"第 (\d+) 圈安装安全眼", part.notes):
        if int(m[1]) not in by_row:
            add("ERROR", None, "EYE_ROUND_MISSING", f"eye round {m[1]} is not in the table")
    if (m := re.search(r"颈部留口：第 (\d+) 圈保留 (\d+) 针", part.notes)):
        if not rows or rows[-1].row != int(m[1]) or rows[-1].stitches != int(m[2]):
            add("ERROR", None, "NOTE_NECK_OPENING", f"notes {m[0]!r} vs last row {rows[-1].row}/{rows[-1].stitches}")
    if (m := re.search(r"帽围 (\d+) 针", part.notes)) and int(m[1]) != peak:
        add("ERROR", None, "NOTE_HAT_ROUND", f"notes say 帽围 {m[1]} 针, table peak {peak}")
    if (m := re.search(r"筒深 (\d+) 圈.*?另有帽顶 (\d+) 圈", part.notes)) and int(m[1]) + int(m[2]) != len(rows):
        add("ERROR", None, "NOTE_HAT_DEPTH", f"筒深 {m[1]} + 帽顶 {m[2]} != {len(rows)} rounds")
    if (m := re.search(r"腰 (\d+) 针开口起针 → 裙摆 (\d+) 针", part.notes)) and rows:
        hem_candidates = {rows[-1].stitches} | ({rows[-2].stitches} if len(rows) > 1 else set())
        if rows[0].stitches != int(m[1]) or int(m[2]) not in hem_candidates:
            add("ERROR", None, "NOTE_SKIRT", f"notes {m[0]!r} vs table {rows[0].stitches}→{sorted(hem_candidates)}")


def check_markdown(md: str) -> Report:
    pattern = parse_markdown(md)
    out: list[Finding] = []
    stats = {"rows": 0, "expanded": 0, "attached_starts": 0,
             "closings": {"cinched": 0, "open_tail_for_sewing": 0, "declared_open": 0, "none": 0}}
    names = [p.name for p in pattern.parts]
    if len(set(names)) != len(names):
        out.append(Finding("ERROR", "*", None, "DUP_PART", str(names)))
    for part in pattern.parts:
        _check_part(part, out, stats)
    parts = {p.name: p for p in pattern.parts}
    add = lambda level, code, msg, part="装配": out.append(Finding(level, part, None, code, msg))  # noqa: E731

    # ── header totals ──
    total_st = sum(r.stitches * p.quantity for p in pattern.parts for r in p.rows)
    total_rounds = sum(len(p.rows) * p.quantity for p in pattern.parts)
    pieces = sum(p.quantity for p in pattern.parts)
    work = next((h for h in pattern.header if h.startswith("工作量：")), None)
    if work is None:
        add("ERROR", "WORKLOAD_MISSING", "no 工作量 line", "*")
    else:
        m = re.match(r"^工作量：(\d+) 个实体部件 · ([\d,]+) 针 · 基础操作估时 (\d+) 分钟（约 ([\d.]+) 小时）$", work)
        if not m:
            add("ERROR", "WORKLOAD_FORMAT", work, "*")
        else:
            expected_min = max(30, round((total_st * 6.5 + total_rounds * 10.0) / 60.0))
            got = (int(m[1]), int(m[2].replace(",", "")), int(m[3]))
            if got != (pieces, total_st, expected_min):
                add("ERROR", "WORKLOAD_TOTALS",
                    f"header {got} vs recomputed pieces/stitches/minutes {(pieces, total_st, expected_min)}", "*")
    stats.update(total_stitches=total_st, total_physical_rounds=total_rounds, pieces=pieces)

    # ── materials: yarn rows must add up to the stated subtotal ──
    grams = meters = 0.0
    yarn_rows = 0
    for item, quantity in pattern.materials:
        if item.startswith("毛线 · "):
            m = re.match(r"^约 ([\d.]+)g（≈([\d.]+)m）", quantity)
            if not m:
                add("ERROR", "YARN_ROW_FORMAT", f"{item}: {quantity}", "材料")
                continue
            grams += float(m[1])
            meters += float(m[2])
            yarn_rows += 1
    if (m := re.match(r"^毛线小计：([\d.]+)g / ([\d.]+)m；含 ([\d.]+)% 预留", pattern.material_summary)):
        if abs(float(m[1]) - grams) > 0.06 * max(1, yarn_rows) or abs(float(m[2]) - meters) > 0.06 * max(1, yarn_rows):
            add("ERROR", "YARN_SUBTOTAL", f"subtotal {m[1]}g/{m[2]}m vs rows {grams:.2f}g/{meters:.2f}m", "材料")
        stats.update(yarn_grams=float(m[1]), yarn_meters=float(m[2]), waste_percent=float(m[3]))
    else:
        add("ERROR", "YARN_SUBTOTAL_MISSING", pattern.material_summary or "(none)", "材料")

    # ── assembly ──
    steps = []
    for i, line in enumerate(pattern.assembly, 1):
        m = re.match(r"^(\d+)\. (.*)$", line)
        if not m or int(m[1]) != i:
            add("ERROR", "ASSEMBLY_NUMBERING", f"line {i}: {line[:40]!r}")
            steps.append(line)
        else:
            steps.append(m[2])
    stats["assembly_steps"] = len(steps)

    def index_of(pattern_text: str) -> int | None:
        return next((i for i, s in enumerate(steps) if re.search(pattern_text, s)), None)

    has_head = "头部" in parts or "头身（一体）" in parts
    eye_step = index_of(r"安全眼")
    # "身体未填棉" in the skirt try-on step is a precondition, not the stuffing step.
    stuff_step = index_of(r"填充棉花|(?<!未)填棉")
    first_sew = index_of(r"缝合到|缝合在|接合到|缝合；|缝合固定")
    if has_head:
        if eye_step is None:
            add("GAP", "EYES_NOT_IN_ASSEMBLY", "no assembly step mentions safety eyes")
        elif stuff_step is not None and eye_step > stuff_step:
            add("ERROR", "EYES_AFTER_STUFFING", f"eye step {eye_step + 1} comes after stuffing step {stuff_step + 1}")
        elif first_sew is not None and eye_step > first_sew:
            add("ERROR", "EYES_AFTER_SEWING", f"eye step {eye_step + 1} comes after sewing step {first_sew + 1}")
        eye_notes = [p for p in pattern.parts if "安装安全眼" in p.notes]
        if not eye_notes:
            add("GAP", "EYE_ROUND_NOT_IN_PART_NOTES", "assembly refers to the part note for the eye round, none has one")
    if stuff_step is None:
        add("GAP", "NO_STUFFING_STEP", "no assembly step mentions stuffing")
    elif first_sew is not None and stuff_step > first_sew:
        add("ERROR", "STUFF_AFTER_SEWING", f"stuffing step {stuff_step + 1} after sewing step {first_sew + 1}")
    try_on = index_of(r"先试套")
    final_skirt = index_of(r"预先套入.*裙筒|裙筒腰部.*套入")
    if "裙子" in parts and not parts["裙子"].rows[0].notes.startswith("BLO("):
        if try_on is None:
            add("GAP", "SKIRT_NO_TRY_ON", "ring skirt without a try-on step")
        else:
            if try_on != 0:
                add("ERROR", "SKIRT_TRY_ON_NOT_FIRST", f"try-on is step {try_on + 1}")
            if stuff_step is not None and try_on > stuff_step:
                add("ERROR", "SKIRT_TRY_ON_AFTER_STUFFING", "try-on after stuffing")
        if final_skirt is None:
            add("GAP", "SKIRT_NO_FIX_STEP", "ring skirt is never fixed in the assembly")

    # numeric anchors in assembly prose
    def finish_edge(name: str) -> int | None:
        return parts[name].rows[-1].stitches if name in parts and parts[name].rows else None

    for step in steps:
        for name in ("手臂", "腿部", "尾巴", "耳朵"):
            m = re.search(rf"{name}.*?（开口 (\d+) 针", step)
            if m and name in parts and finish_edge(name) != int(m[1]):
                add("ERROR", "ASSEMBLY_OPENING_COUNT", f"{step[:30]}… says {m[1]}, {name} last round has {finish_edge(name)}")
        if (m := re.search(r"帽口 (\d+) 针", step)) and "帽子" in parts and finish_edge("帽子") != int(m[1]):
            add("ERROR", "ASSEMBLY_HAT_COUNT", f"says {m[1]}, hat last round {finish_edge('帽子')}")
        if (m := re.search(r"裙筒腰部（(\d+) 针开口）", step)) and "裙子" in parts:
            if parts["裙子"].rows[0].stitches != int(m[1]):
                add("ERROR", "ASSEMBLY_SKIRT_COUNT", f"says {m[1]}, skirt row 1 has {parts['裙子'].rows[0].stitches}")
        if (m := re.search(r"将头部第 (\d+) 圈颈口（(\d+) 针）与身体顶部第 (\d+) 圈开口（(\d+) 针）缝合", step)):
            head, body = parts.get("头部"), parts.get("身体")
            ok = (head and body and head.rows[-1].row == int(m[1]) and head.rows[-1].stitches == int(m[2])
                  and body.rows[-1].row == int(m[3]) and body.rows[-1].stitches == int(m[4]))
            if not ok:
                add("ERROR", "ASSEMBLY_NECK_ANCHOR", step[:60])
            stats["neck_anchor_checked"] = True
        if (m := re.search(r"钩(.+?)第 (\d+) 圈时，按该圈 FLO 操作式只挑第 (\d+) 圈的前半针，保留其第 1–(\d+) 针的后半针。"
                           r".*?将(.+?)第 1 圈钩入这些后半针，每个针目钩 1 短针，共 (\d+) 针", step)):
            target, source = parts.get(m[1]), parts.get(m[5])
            n = int(m[4])
            problems = []
            if target is None or source is None:
                problems.append("part missing")
            else:
                rows = {r.row: r for r in target.rows}
                base, reserve = rows.get(int(m[3])), rows.get(int(m[2]))
                if base is None or reserve is None or reserve.row != base.row + 1:
                    problems.append("rows missing / not adjacent")
                else:
                    if base.stitches != n or int(m[6]) != n:
                        problems.append(f"base row has {base.stitches}, text says {n}/{m[6]}")
                    if "FLO" not in reserve.notes:
                        problems.append(f"reservation row note has no FLO: {reserve.notes!r}")
                    if reserve.row == target.rows[-1].row and _CLOSE_TIGHT.search(reserve.notes):
                        problems.append("reservation row is the cinched last row")
                if not source.rows or source.rows[0].stitches != n or "BLO" not in source.rows[0].notes:
                    problems.append("skirt row 1 does not take n BLO stitches")
            if problems:
                add("ERROR", "ASSEMBLY_SKIRT_ANCHOR", "; ".join(problems))
            stats["skirt_anchor_checked"] = True
    # every non-root part should be mentioned by some assembly step
    roots = {"身体", "头身（一体）"}
    for name in parts:
        if name in roots:
            continue
        key = {"帽子": "帽", "裙子": "裙"}.get(name, name)
        if not any(key in s for s in steps[1:] + steps[:1] if "试套" not in s and "安全眼" not in s
                   and "绣" not in s and "针塑形" not in s):
            add("GAP", "PART_NOT_ASSEMBLED", f"no assembly step attaches {name}")
    return Report(pattern, out, stats)


if __name__ == "__main__":
    import sys

    text = open(sys.argv[1], encoding="utf-8").read()
    report = check_markdown(text)
    for finding in report.findings:
        print(finding)
    print(report.stats)
