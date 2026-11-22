# working-path area — running notes (scratch, not the report)

Audited tree: main @ 6c88b7df5d53c18d4c8190288419faeb02cc1b13
Env: .venv Python 3.12.13, pydantic 2.14.3, reportlab 5.1.0, streamlit 1.67.0
No pdftotext/pypdf available -> PDF text is checked by capturing Paragraph inputs
(Paragraph.getPlainText) and by viewing rendered pages.

## Declared contract (what the code/docs say a compiled plan guarantees)

C1  module docstring working_path.py:1-5 — "checks a declared stitch-site inventory. It does
    not infer garment shape, measure gauge, or establish that a physical piece can be made".
C2  compile_working_path docstring :771 — "Resolve explicit sites, reject reuse/leaks, and
    retain all source indices".
C3  EdgePath docstring :152-156 — transfer of available sites; "Old aliases lose access".
C4  hold() comment :639 — "A reserved path is deliberately not re-reservable under a second name".
C5  check_turned_continuation docstring :745-749 — only same-section ordinary turned rows, order on
    the preceding row only; "does not infer the geometry of an arbitrary pickup path or continuity
    between sections".
C6  roadmap :25 — rejects out-of-range, double booking, half loops without reservation evidence,
    row ends without source, missing rows, positions with undeclared destination.
C7  roadmap :21-23 — BLO/FLO use and unused half loop recorded; binding slip / working stitch /
    turning chain / invisible closure kept apart; seam sides paired position by position;
    buttonhole records skipped sites.
C8  roadmap :125-126 — yarn mode rejects: joining new yarn over a live loop, fastening off at the
    wrong place, weaving a finishing end early, registering the same end twice, missing turn
    across sections.
C9  markdown footer working_path_export.py:174-182 — printed "检查结论" bullets.
C10 route_formula docstring working_path_format.py:41-45 — "Resolved events prevent an alias edge
    from hiding chains, corners or row ends".
C11 working_recipe_export.py:1 — "Readable recipe tables derived from checked routes, not a second
    stitch script".
C12 roadmap :42-44 — UI: 2 MiB limit, duplicate keys / non-finite / unknown format rejected;
    changed upload disables old downloads; failed input or PDF layout keeps previous record.
C13 roadmap :38-40 — CLI never overwrites; PDF derived from the same validated operations.

Declared NON-goals (limits): roadmap :48-53 (no fabric simulation, no cross-section continuity,
half loops / row ends only introduced on demand, "未说明去向为零" only means the ledger closes).

## Already established by lead (not re-derived)
(a) turned-row order check only inside one section; (b) segment route with turn does not flip side;
(c) 1-chain buttonhole retiring 10 unrelated stitches; (d) finish_edge finished_border mid-row;
(e) tracked yarn never fastened off is only a flag.

## Progress log
- p01 alias/ownership: validator HELD on bounds, overlap, hold re-hold, edge_path chains, every consumer
  reaching reserved sites through the original name. Observed: scrambled non-adjacent hold worked as one
  run prints "4X" (formula hides the jump). held_edges in result JSON keeps stale membership after transfer.
- p02 faces/loops/row ends: validator HELD on conjured half loops, double lips, double row ends.
  Accepted: row end at the slip-stitched (joined) end; zig-zag row-end list; both faces of the same
  chain stitches retired as unused_chain_face (variant of lead's d).
- p03 yarn control: state machine HELD on most transitions. Accepted: dangling NewYarn (never used);
  resume after loop stitch was worked over by another strand; NewYarn(RS)+turning chain => first row WS.
- p04 NEW: hook position = last BINDING slip stitch even when working stitches follow it in the same row
  (working_path.py:738). Correct fasten-off/park/seam/continue-chain reference is REJECTED, wrong one ACCEPTED,
  export tells maker to cut at the binding stitch.
- p05 NEW: same-section turned row may start k stitches away from the hook; recipe-PDF row is identical
  for the valid (20..11) and the invalid (10..1) plan.
- p06: interior "row ends" of a split row accepted; one uncut tracked strand hops between unconnected pieces.
- p07 loader: strictness HELD (dup keys, NaN, big ints, nesting, BOM, surrogate, extra keys, bool/int).
  NUL in title accepted. v1 accepts section/row_number/turn/turning_chains on segment routes.
  Wording: dup-key error says "备份 JSON"; CLI says "工序演示未导出" for user plans.
- p08 untrusted strings: Markdown block structure injectable via newlines in title/label/note/review_notes
  (out/injection.md); links/images/HTML neutralised; both PDF exporters escape markup. Legacy PDF drops
  review_notes. Control chars pass through.
- p09 seams: validator HELD on unequal lengths, self/alias seams, consumed/binding sites. Pairing order is taken
  as written (aligned and crossed both accepted; text differs). Loops left by a seam usable only via FreeLoops.
- All nine probes re-run from fresh processes: exit 0, *.rerun.out identical to *.out.
- Stopped probing at the lead's request. REPORT.md could not be written: the harness refuses report files from
  subagents, so the report was returned as the final message instead. Not reached: rendered-PDF check, AppTest,
  timing on pathological sizes.
