"""Independent reader of a dressed-doll `plan.md`, written from the maker's side.

It does NOT import anything from `app`. It reads the Markdown text exactly as exported,
expands every operation string stitch by stitch against the previous row/round, and
derives the foundation working edge from the written foundation sentence.

Stitch semantics used here (standard single-crochet notation, as in the plan legend):
  X = 1 sc in 1 stitch (uses 1, makes 1)        V = 2 sc in the same stitch (uses 1, makes 2)
  W = 3 sc in the same stitch (uses 1, makes 3)  A = sc2tog (uses 2, makes 1)
Foundation working edges derived independently:
  magic ring            : round 1 is worked into the ring -> only plain X allowed, any count
  chain ring of n       : n chain positions, one sc each
  flat chain of n       : first sc in 2nd chain from hook -> n-1 working chains
  oval around chain of n: skip 1 chain -> n-1 workable chains; the two END chains are
                          worked once (3 sc each), the n-3 middle chains are worked on
                          BOTH sides -> working positions = 2 + 2(n-3) = 2n-4, and the
                          standard round is 3 + (n-3) + 3 + (n-3) = 2n stitches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class ReadError(Exception):
    pass


# ---------------------------------------------------------------- expression expansion
_TOK = re.compile(r"\d+|[XVAW]|[(),×]")


def _tokens(text: str) -> list[str]:
    out, pos = [], 0
    text = text.strip()
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOK.match(text, pos)
        if not m:
            raise ReadError(f"unreadable operation text at {text[pos:pos + 12]!r} in {text!r}")
        out.append(m[0])
        pos = m.end()
    return out


def expand(text: str) -> list[str]:
    """Flat list of physical operations, in working order."""
    toks = _tokens(text)
    pos = 0

    def seq() -> list[str]:
        nonlocal pos
        ops = term()
        while pos < len(toks) and toks[pos] == ",":
            pos += 1
            ops += term()
        return ops

    def term() -> list[str]:
        nonlocal pos
        count = 1
        if pos < len(toks) and toks[pos].isdigit():
            count = int(toks[pos])
            pos += 1
        if pos >= len(toks):
            raise ReadError(f"dangling count in {text!r}")
        tok = toks[pos]
        pos += 1
        if tok == "(":
            inner = seq()
            if pos >= len(toks) or toks[pos] != ")":
                raise ReadError(f"missing ) in {text!r}")
            pos += 1
        elif tok in "XVAW":
            inner = [tok]
        else:
            raise ReadError(f"unexpected {tok!r} in {text!r}")
        inner = inner * count
        if pos < len(toks) and toks[pos] == "×":
            pos += 1
            if pos >= len(toks) or not toks[pos].isdigit():
                raise ReadError(f"× without a count in {text!r}")
            inner = inner * int(toks[pos])
            pos += 1
        return inner

    ops = seq()
    if pos != len(toks):
        raise ReadError(f"trailing text in {text!r}")
    return ops


USES = {"X": 1, "V": 1, "W": 1, "A": 2}
MAKES = {"X": 1, "V": 2, "W": 3, "A": 1}


def work_round(ops: list[str], available: int) -> tuple[int, list[list[int]]]:
    """Walk the previous row/round. Returns (stitches made, parents of each new stitch).

    Raises ReadError as soon as an operation needs a stitch the previous row does not offer
    or when stitches are left unworked.
    """
    pointer = 0
    parents: list[list[int]] = []
    for i, op in enumerate(ops, 1):
        need = USES[op]
        if pointer + need > available:
            raise ReadError(f"operation #{i} ({op}) needs stitch {pointer + need} but only {available} exist")
        src = list(range(pointer, pointer + need))
        pointer += need
        parents.extend([src] * MAKES[op])
    if pointer != available:
        raise ReadError(f"{available - pointer} stitch(es) of the previous row/round are left unworked")
    return len(parents), parents


# ---------------------------------------------------------------- markdown reading
@dataclass
class Row:
    label: str
    numbers: list[int]
    section: str
    raw_operation: str
    turn: bool
    loops: str
    expression: str
    stated: int
    note: str


@dataclass
class Part:
    name: str
    quantity: int
    role: str
    color: str
    foundation_text: str
    unit: str
    rows: list[Row] = field(default_factory=list)
    finish: str = ""
    fitting: list[str] = field(default_factory=list)
    join_target: str | None = None
    join_text: str | None = None
    # derived
    kind: str = ""
    chains: int = 0
    counts: list[int] = field(default_factory=list)       # stitches after each step (expanded)
    parents: list[list[list[int]]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class Plan:
    header: list[str]
    legend: str
    checkpoints: list[str]
    summary: list[tuple[str, int, str, str]]
    parts: list[Part]
    assembly: list[str]
    limitations: list[str]


def _cells(line: str) -> list[str]:
    inner = line.strip()
    assert inner.startswith("|") and inner.endswith("|"), line
    parts = re.split(r"(?<!\\)\|", inner[1:-1])
    return [p.strip() for p in parts]


def read_plan(md: str) -> Plan:
    lines = md.split("\n")
    idx = {"checkpoints": None, "summary": None, "assembly": None, "limits": None}
    for i, line in enumerate(lines):
        if line == "## 先检查这些部位":
            idx["checkpoints"] = i
        elif line == "## 部件与连接":
            idx["summary"] = i
        elif line == "## 装配顺序":
            idx["assembly"] = i
        elif line == "## 尚未验证与未覆盖":
            idx["limits"] = i
    if None in idx.values():
        raise ReadError(f"missing top-level section(s): {idx}")
    header = [x for x in lines[: idx["checkpoints"]] if x.strip()]
    legend = next((x for x in header if x.startswith("记号：")), "")
    checkpoints = [x[2:] for x in lines[idx["checkpoints"]: idx["summary"]] if x.startswith("- ")]
    summary = []
    part_start = None
    for i in range(idx["summary"] + 1, idx["assembly"]):
        line = lines[i]
        if line.startswith("## "):
            part_start = i
            break
        if line.startswith("|") and not line.startswith("|---") and "部件" not in line.split("|")[1]:
            c = _cells(line)
            summary.append((c[0], int(c[1]), c[2], c[3]))
    parts: list[Part] = []
    block: list[str] = []
    for line in lines[part_start: idx["assembly"]]:
        if line.startswith("## ") and block:
            parts.append(_read_part(block))
            block = []
        block.append(line)
    if block:
        parts.append(_read_part(block))
    assembly = []
    for line in lines[idx["assembly"] + 1: idx["limits"]]:
        m = re.match(r"(\d+)\. (.*)", line)
        if m:
            assert int(m[1]) == len(assembly) + 1, "assembly numbering is not consecutive"
            assembly.append(m[2])
    limitations = [x[2:] for x in lines[idx["limits"] + 1:] if x.startswith("- ")]
    return Plan(header, legend, checkpoints, summary, parts, assembly, limitations)


def _read_part(block: list[str]) -> Part:
    m = re.fullmatch(r"## (.+) × (\d+)", block[0])
    if not m:
        raise ReadError(f"unreadable part heading {block[0]!r}")
    body = [x for x in block[1:] if x.strip()]
    m2 = re.fullmatch(r"用途：(.+)；颜色：(.+)。", body[0])
    if not m2:
        raise ReadError(f"unreadable use/colour line {body[0]!r}")
    part = Part(name=m[1], quantity=int(m[2]), role=m2[1], color=m2[2], foundation_text=body[1], unit="")
    head = _cells(body[2])
    part.unit = head[0]
    assert head == [part.unit, "段落", f"本{part.unit}操作式", f"本{part.unit}针数", "提示"], head
    assert body[3].startswith("|---")
    i = 4
    while i < len(body) and body[i].startswith("|"):
        c = _cells(body[i])
        if len(c) != 5:
            raise ReadError(f"table row with {len(c)} cells: {body[i]!r}")
        label, section, op, stated, note = c
        if "–" in label:
            a, b = label.split("–")
            numbers = list(range(int(a), int(b) + 1))
        else:
            numbers = [int(label)]
        turn = False
        loops = "both"
        rest = op
        if rest.startswith("先 CH 1，翻转；"):
            turn = True
            rest = rest[len("先 CH 1，翻转；"):]
        if rest.startswith("只挑前半针；"):
            loops = "front"
            rest = rest[len("只挑前半针；"):]
        elif rest.startswith("只挑后半针；"):
            loops = "back"
            rest = rest[len("只挑后半针；"):]
        part.rows.append(Row(label, numbers, section, op, turn, loops, rest, int(stated), note))
        i += 1
    for line in body[i:]:
        if line.startswith("收尾："):
            part.finish = line[3:]
        elif line.startswith("- 试合："):
            part.fitting.append(line[5:])
        elif line.startswith("连接到 "):
            target, _, text = line[4:].partition("：")
            part.join_target, part.join_text = target, text
        else:
            raise ReadError(f"unexpected line in part {part.name}: {line!r}")
    _derive(part)
    return part


def _derive(part: Part) -> None:
    t = part.foundation_text
    working_edge: int | None
    if t.startswith("魔法环起针"):
        part.kind, part.chains, working_edge = "magic_ring", 0, None
    elif (m := re.match(r"锁 (\d+) 针，不扭转地引拔连接成环", t)):
        part.kind, part.chains = "chain_ring", int(m[1])
        working_edge = part.chains
    elif (m := re.match(r"锁 (\d+) 针；从钩上倒数第 2 针开始，沿锁针回钩第 1 行", t)):
        part.kind, part.chains = "flat_chain", int(m[1])
        working_edge = part.chains - 1
    elif (m := re.match(r"锁 (\d+) 针；从倒数第 2 针开始，在近端锁针钩 3 短针，沿直边 (\d+) 针各钩 1 短针，"
                        r"远端锁针钩 3 短针，转到锁针另一侧，沿直边 (\d+) 针各钩 1 短针", t)):
        part.kind, part.chains = "oval_chain", int(m[1])
        side_a, side_b = int(m[2]), int(m[3])
        if side_a != part.chains - 3 or side_b != part.chains - 3:
            part.problems.append(f"oval sentence: straight sides {side_a}/{side_b} but a chain of "
                                 f"{part.chains} has {part.chains - 3} middle chains")
        working_edge = 2 + side_a + side_b
    else:
        part.problems.append(f"foundation sentence not understood: {t!r}")
        return
    expected_no = 1
    available = working_edge
    for row in part.rows:
        for n in row.numbers:
            if n != expected_no:
                part.problems.append(f"{part.unit} numbering jumps to {n}, expected {expected_no}")
            expected_no = n + 1
            try:
                ops = expand(row.expression)
            except ReadError as exc:
                part.problems.append(f"{part.unit} {n}: {exc}")
                return
            if n == 1:
                if row.turn:
                    part.problems.append("row 1 says to chain 1 and turn before any stitch exists")
                if part.kind == "magic_ring":
                    if set(ops) != {"X"}:
                        part.problems.append("magic-ring round 1 must be plain sc into the ring")
                    made, parents = len(ops), [[i] for i in range(len(ops))]
                elif part.kind == "oval_chain":
                    k = part.chains - 3
                    if ops != ["W"] + ["X"] * k + ["W"] + ["X"] * k:
                        part.problems.append(f"oval round 1 is {row.expression!r}, expected W,{k}X,W,{k}X")
                    if len(ops) and sum(MAKES[o] for o in ops) != 2 * part.chains:
                        part.problems.append("oval round 1 does not make 2n stitches")
                    try:
                        made, parents = work_round(ops, available)
                    except ReadError as exc:
                        part.problems.append(f"{part.unit} 1: {exc}")
                        return
                else:
                    if set(ops) - ({"X", "V"} if part.kind == "flat_chain" else {"X"}):
                        part.problems.append(f"{part.unit} 1 on a {part.kind} uses unexpected stitches {set(ops)}")
                    try:
                        made, parents = work_round(ops, available)
                    except ReadError as exc:
                        part.problems.append(f"{part.unit} 1: {exc}")
                        return
            else:
                if part.unit == "行" and not row.turn:
                    part.problems.append(f"行 {n}: flat row without a turning chain/turn instruction")
                if part.unit == "圈" and row.turn:
                    part.problems.append(f"圈 {n}: spiral round with a turn instruction")
                try:
                    made, parents = work_round(ops, available)
                except ReadError as exc:
                    part.problems.append(f"{part.unit} {n}: {exc}")
                    return
            if made != row.stated:
                part.problems.append(f"{part.unit} {n}: text makes {made} stitches, table says {row.stated}")
            part.counts.append(made)
            part.parents.append(parents)
            available = made


def ancestors_at(part: Part, target_round: int, base_round: int) -> list[set[int]]:
    """For each stitch of `target_round` (1-based), the set of `base_round` stitches it descends from."""
    result = [{i} for i in range(part.counts[base_round - 1])]
    for rnd in range(base_round + 1, target_round + 1):
        parents = part.parents[rnd - 1]
        result = [set().union(*(result[p] for p in ps)) for ps in parents]
    return result
