"""Command-line entry point for PuffinTest test modules."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType

from .runner import discover_tests, run_async_tests


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return timeout


def _load_module(path: Path, index: int) -> ModuleType:
    module_name = f"_puffintest_file_{index}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="puffintest",
        description="Run PuffinTest cases declared in Python files.",
    )
    parser.add_argument("files", nargs="+", type=Path, help="test files to load")
    parser.add_argument(
        "--filter", dest="name_filter", help="run case names containing this text"
    )
    parser.add_argument(
        "--tag", dest="tag_filter", help="run cases carrying this tag"
    )
    parser.add_argument(
        "--fail-fast", action="store_true", help="stop after the first failed case"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered cases without executing test cases",
    )
    parser.add_argument(
        "--case-timeout",
        type=_positive_timeout,
        help="timeout in seconds for each awaited test body",
    )
    args = parser.parse_args(argv)

    cases = []
    for index, path in enumerate(args.files):
        try:
            resolved_path = path.resolve(strict=True)
            parent = str(resolved_path.parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            module = _load_module(resolved_path, index)
        except Exception as error:
            parser.error(f"could not load {path}: {type(error).__name__}: {error}")
        cases.extend(discover_tests(module))

    if args.list:
        normalized_filter = args.name_filter.casefold() if args.name_filter else None
        normalized_tag = args.tag_filter.casefold() if args.tag_filter else None
        listed = 0
        for case in cases:
            if (
                normalized_filter is not None
                and normalized_filter not in case.name.casefold()
            ):
                continue
            if normalized_tag is not None and not any(
                normalized_tag == tag.casefold() for tag in case.tags
            ):
                continue
            listed += 1
            if case.skip_reason is None:
                print(case.name)
            else:
                print(f"{case.name} [skipped: {case.skip_reason}]")
        if listed == 0:
            if normalized_filter is not None and normalized_tag is not None:
                print(
                    f"No test cases matched name {args.name_filter!r} "
                    f"and tag {args.tag_filter!r}"
                )
            elif normalized_filter is not None:
                print(f"No test cases matched name {args.name_filter!r}")
            elif normalized_tag is not None:
                print(f"No test cases matched tag {args.tag_filter!r}")
            else:
                print("No test cases were found")
            return 1
        print(f"\n{listed} case(s)")
        return 0

    return asyncio.run(
        run_async_tests(
            cases,
            name_filter=args.name_filter,
            tag_filter=args.tag_filter,
            fail_fast=args.fail_fast,
            case_timeout=args.case_timeout,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
