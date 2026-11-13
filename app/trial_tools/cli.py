"""Physical trial cli."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import (
    analyze_trial_directory,
)
from .drafts import (
    create_trial_draft,
    upgrade_trial_record_from_bytes,
)
from .external import (
    load_curated_external_evidence,
    load_external_evidence,
    summarize_external_evidence,
)
from .io import (
    _read_bytes,
    _read_json,
    write_json,
)
from .schemas import (
    MAX_PATTERN_BYTES,
    MAX_TRIAL_BYTES,
    TrialDataError,
    TrialRecord,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crochet2pattern-trials",
        description="创建实体试钩记录并分析尺寸、用线和工时偏差",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="从图解 JSON 创建绑定哈希的试钩草稿")
    init.add_argument("--pattern", required=True)
    init.add_argument("--trial-id", required=True)
    init.add_argument("--maker-id", required=True, help="稳定的匿名制作者 ID")
    init.add_argument(
        "--cohort",
        choices=("calibration", "validation"),
        default="calibration",
        help="校准集或独立留出验证集；默认 calibration",
    )
    init.add_argument("--out", required=True, help="建议使用 *.trial.json")
    init.add_argument("--force", action="store_true", help="允许覆盖已有草稿文件")
    migrate = commands.add_parser("migrate", help="核对原图解后升级旧试钩记录的设计身份，保留测量")
    migrate.add_argument("--pattern", required=True, help="与旧记录 SHA 完全一致的原图解 JSON")
    migrate.add_argument("--record", required=True, help="原始 *.trial.json")
    migrate.add_argument("--out", required=True, help="升级后的新记录文件，不可覆盖输入文件")
    migrate.add_argument("--force", action="store_true", help="允许覆盖已有输出，不允许覆盖输入")
    analyze = commands.add_parser("analyze", help="分析目录内全部 *.trial.json")
    analyze.add_argument("--records", required=True)
    analyze.add_argument("--out", help="JSON 报告路径；省略则输出到 stdout")
    external_context = analyze.add_mutually_exclusive_group()
    external_context.add_argument(
        "--external-evidence",
        help="外部证据 JSON；只附加背景，不参与校准",
    )
    external_context.add_argument(
        "--curated-external-evidence",
        action="store_true",
        help="附加发行包内置精选证据；只作背景，不参与校准",
    )
    analyze.add_argument(
        "--allow-insufficient",
        action="store_true",
        help="样本不足时返回 0；报告仍保持 calibration_ready=false",
    )
    analyze.add_argument(
        "--require-validation",
        action="store_true",
        help="独立验证集样本不足或与校准图解重叠时返回 2",
    )
    external = commands.add_parser(
        "external-report",
        help="验证并汇总外部试钩证据；不需要本地试钩记录",
    )
    evidence_source = external.add_mutually_exclusive_group(required=True)
    evidence_source.add_argument("--evidence", help="用户提供的外部证据 JSON")
    evidence_source.add_argument(
        "--curated",
        action="store_true",
        help="使用发行包内置、带来源边界的精选证据",
    )
    external.add_argument("--out", help="JSON 报告路径；省略则输出到 stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            output_path = Path(args.out)
            if output_path.exists() and not args.force:
                raise TrialDataError(f"refusing to overwrite existing trial: {output_path}")
            draft = create_trial_draft(
                args.pattern,
                trial_id=args.trial_id,
                maker_id=args.maker_id,
                cohort=args.cohort,
            )
            path = write_json(draft, output_path)
            print(f"试钩草稿: {path}", file=sys.stderr)
            return 0
        if args.command == "migrate":
            output_path = Path(args.out).resolve()
            for value in (args.pattern, args.record):
                source_path = Path(value).resolve()
                if output_path == source_path or (output_path.exists() and output_path.samefile(source_path)):
                    raise TrialDataError("升级输出不可覆盖原图解或原记录，请选择新文件")
            if output_path.exists() and not args.force:
                raise TrialDataError(f"refusing to overwrite existing trial: {output_path}")
            try:
                record = TrialRecord.model_validate(_read_json(Path(args.record), MAX_TRIAL_BYTES))
            except ValueError as exc:
                raise TrialDataError(f"invalid trial record: {exc}") from exc
            blob = _read_bytes(Path(args.pattern), MAX_PATTERN_BYTES)
            upgraded = upgrade_trial_record_from_bytes(blob, record)
            from app.utils.output_files import write_outputs

            output_path.parent.mkdir(parents=True, exist_ok=True)
            write_outputs({output_path: upgraded.model_dump_json(indent=2).encode("utf-8")})
            print(f"试钩记录已升级: {output_path}", file=sys.stderr)
            return 0
        if args.command == "external-report":
            evidence = (
                load_curated_external_evidence()
                if args.curated
                else load_external_evidence(args.evidence)
            )
            report = summarize_external_evidence(evidence)
            if args.out:
                path = write_json(report, args.out)
                print(f"外部证据报告: {path}", file=sys.stderr)
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            coverage = report["coverage"]
            print(
                f"外部证据: sources={coverage['sources']} · "
                f"observations={coverage['observations']} · calibration=false",
                file=sys.stderr,
            )
            return 0
        report = analyze_trial_directory(
            args.records,
            args.external_evidence,
            curated_external_evidence=args.curated_external_evidence,
        )
    except (TrialDataError, OSError) as exc:
        # write_json 的目标路径不可写也走同一条友好错误出口，而不是 traceback。
        label = "试钩数据无效" if isinstance(exc, TrialDataError) else "试钩文件读写失败"
        print(f"{label}: {exc}", file=sys.stderr)
        return 1
    if args.out:
        try:
            path = write_json(report, args.out)
        except OSError as exc:
            print(f"试钩文件读写失败: {exc}", file=sys.stderr)
            return 1
        print(f"试钩报告: {path}", file=sys.stderr)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    summary = report["summary"]
    print(
        f"试钩分析: completed={summary['completed']} · "
        f"eligible={summary['calibration_eligible']} · "
        f"time_eligible={summary['time_calibration_eligible']} · "
        f"ready={summary['calibration_ready']} · "
        f"validation_ready={summary['independent_validation_sample_ready']}",
        file=sys.stderr,
    )
    analysis_ready = summary["calibration_ready"] and (
        not args.require_validation
        or summary["independent_validation_sample_ready"]
    )
    return 0 if analysis_ready or args.allow_insufficient else 2
