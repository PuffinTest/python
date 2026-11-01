"""Execution and text reporting for PuffinTest cases."""

from __future__ import annotations

import asyncio
import inspect
import traceback
from collections.abc import Iterable
from types import ModuleType
from typing import Callable

from .api import AssertionFailure, TestCase


def _display(value: object) -> str:
    try:
        return repr(value)
    except Exception as error:  # repr can be user-defined and may itself fail
        return f"<repr failed: {type(error).__name__}>"


def _print_failure(
    case: TestCase, error: BaseException, *, phase: str | None = None
) -> None:
    suffix = f" ({phase})" if phase is not None else ""
    print(f"FAIL  {case.name}{suffix}")
    if isinstance(error, AssertionFailure):
        print(f"      {error.message}")
        if error.has_values:
            print(f"      Expected: {_display(error.expected)}")
            print(f"      Actual:   {_display(error.actual)}")
        print(f"      {error.filename}:{error.line}")
        return

    print(f"      {type(error).__name__}: {error}")
    traceback_frames = traceback.extract_tb(error.__traceback__)
    if traceback_frames:
        frame = traceback_frames[-1]
        print(f"      {frame.filename}:{frame.lineno}")


def _invoke_sync(callback: Callable[[], object]) -> None:
    outcome = callback()
    if inspect.isawaitable(outcome):
        if inspect.iscoroutine(outcome):
            outcome.close()
        raise TypeError("An async callback requires run_async_tests()")


def _execute_case(
    case: TestCase,
    before_each: Callable[[], object] | None,
    after_each: Callable[[], object] | None,
) -> list[tuple[str, Exception]]:
    errors: list[tuple[str, Exception]] = []
    setup_succeeded = False
    try:
        if before_each is not None:
            _invoke_sync(before_each)
        setup_succeeded = True
        _invoke_sync(case.function)
    except Exception as error:
        phase = "before_each" if not setup_succeeded else "test"
        errors.append((phase, error))
    finally:
        if setup_succeeded and after_each is not None:
            try:
                _invoke_sync(after_each)
            except Exception as error:
                errors.append(("after_each", error))
    return errors


async def _invoke_async(
    callback: Callable[[], object], *, timeout: float | None = None
) -> None:
    outcome = callback()
    if inspect.isawaitable(outcome):
        if timeout is None:
            await outcome
        else:
            task = asyncio.ensure_future(outcome)
            try:
                await asyncio.wait_for(task, timeout=timeout)
            except asyncio.TimeoutError as error:
                if task.cancelled():
                    raise TimeoutError(
                        f"Case exceeded its {timeout:g} second timeout"
                    ) from error
                raise


async def _execute_async_case(
    case: TestCase,
    before_each: Callable[[], object] | None,
    after_each: Callable[[], object] | None,
    case_timeout: float | None,
) -> list[tuple[str, Exception]]:
    errors: list[tuple[str, Exception]] = []
    setup_succeeded = False
    try:
        if before_each is not None:
            await _invoke_async(before_each)
        setup_succeeded = True
        await _invoke_async(case.function, timeout=case_timeout)
    except Exception as error:
        phase = "before_each" if not setup_succeeded else "test"
        errors.append((phase, error))
    finally:
        if setup_succeeded and after_each is not None:
            try:
                await _invoke_async(after_each)
            except Exception as error:
                errors.append(("after_each", error))
    return errors


def _print_case_errors(case: TestCase, errors: list[tuple[str, Exception]]) -> None:
    for phase, error in errors:
        if phase == "test":
            _print_failure(case, error)
        else:
            _print_failure(case, error, phase=phase)


def _matches_filters(
    case: TestCase, normalized_name: str | None, normalized_tag: str | None
) -> bool:
    if normalized_name is not None and normalized_name not in case.name.casefold():
        return False
    if normalized_tag is not None and not any(
        normalized_tag == tag.casefold() for tag in case.tags
    ):
        return False
    return True


def _print_no_cases(name_filter: str | None, tag_filter: str | None) -> None:
    if name_filter and tag_filter:
        print(
            f"No test cases matched name {name_filter!r} and tag {tag_filter!r}"
        )
    elif name_filter:
        print(f"No test cases matched name {name_filter!r}")
    elif tag_filter:
        print(f"No test cases matched tag {tag_filter!r}")
    else:
        print("No test cases were found")


def discover_tests(module: ModuleType) -> tuple[TestCase, ...]:
    """Collect test cases declared in ``module`` in declaration order.

    Finds values created by :func:`puffintest.test` and
    :func:`puffintest.test_cases`. Imported test cases from other modules are
    ignored. Repeated references to the same case are returned once.
    """
    discovered: list[TestCase] = []
    seen: set[int] = set()
    for value in vars(module).values():
        candidates = (value,) if isinstance(value, TestCase) else value
        if not isinstance(candidates, (tuple, list)):
            continue
        for candidate in candidates:
            if not isinstance(candidate, TestCase):
                continue
            if candidate.function.__module__ != module.__name__:
                continue
            identity = id(candidate)
            if identity not in seen:
                discovered.append(candidate)
                seen.add(identity)
    return tuple(discovered)


def run_tests(
    cases: Iterable[TestCase],
    *,
    name_filter: str | None = None,
    tag_filter: str | None = None,
    fail_fast: bool = False,
    before_each: Callable[[], object] | None = None,
    after_each: Callable[[], object] | None = None,
) -> int:
    """Run each case, print a summary, and return 0 on success or 1 on failure.

    Each case is isolated: a failure stops that case and the next case runs.
    Cases decorated with a skip reason are reported without being called.
    ``name_filter`` selects case names containing the text, ignoring case.
    ``tag_filter`` selects cases with an exact tag match, ignoring case.
    With ``fail_fast=True``, stop after the first failed case. Return 1 when
    a selected case fails or when a nonempty filter matches no cases.
    Hooks run around every selected non-skipped case. Teardown runs after a
    case failure, but not when setup itself fails.
    """
    passed = 0
    failed = 0
    skipped = 0
    processed = 0
    normalized_filter = name_filter.casefold() if name_filter else None
    normalized_tag = tag_filter.casefold() if tag_filter else None
    for case in cases:
        if not _matches_filters(case, normalized_filter, normalized_tag):
            continue
        processed += 1
        if case.skip_reason is not None:
            skipped += 1
            print(f"SKIP  {case.name} ({case.skip_reason})")
            continue
        errors = _execute_case(case, before_each, after_each)
        if errors:
            failed += 1
            _print_case_errors(case, errors)
            if fail_fast:
                break
        else:
            passed += 1
            print(f"PASS  {case.name}")

    print(f"\n{processed} processed: {passed} passed, {failed} failed, {skipped} skipped")
    if processed == 0:
        _print_no_cases(name_filter, tag_filter)
        return 1
    return 1 if failed else 0


async def run_async_tests(
    cases: Iterable[TestCase],
    *,
    name_filter: str | None = None,
    tag_filter: str | None = None,
    fail_fast: bool = False,
    before_each: Callable[[], object] | None = None,
    after_each: Callable[[], object] | None = None,
    case_timeout: float | None = None,
) -> int:
    """Run synchronous and asynchronous test cases sequentially.

    Async cases are awaited before they are reported. Filtering, skipping,
    fail-fast behavior, hooks, output, and return codes match :func:`run_tests`.
    ``case_timeout`` limits each awaited test body; setup and teardown hooks
    and synchronous test bodies are not timed.
    """
    if case_timeout is not None and case_timeout <= 0:
        raise ValueError("case_timeout must be greater than zero")
    passed = 0
    failed = 0
    skipped = 0
    processed = 0
    normalized_filter = name_filter.casefold() if name_filter else None
    normalized_tag = tag_filter.casefold() if tag_filter else None
    for case in cases:
        if not _matches_filters(case, normalized_filter, normalized_tag):
            continue
        processed += 1
        if case.skip_reason is not None:
            skipped += 1
            print(f"SKIP  {case.name} ({case.skip_reason})")
            continue
        errors = await _execute_async_case(
            case, before_each, after_each, case_timeout
        )
        if errors:
            failed += 1
            _print_case_errors(case, errors)
            if fail_fast:
                break
        else:
            passed += 1
            print(f"PASS  {case.name}")

    print(f"\n{processed} processed: {passed} passed, {failed} failed, {skipped} skipped")
    if processed == 0:
        _print_no_cases(name_filter, tag_filter)
        return 1
    return 1 if failed else 0
