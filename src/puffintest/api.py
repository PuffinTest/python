"""Test declarations and expectation helpers."""

from __future__ import annotations

import inspect
import math
import re
from collections.abc import Iterable, Sized
from dataclasses import dataclass
from typing import Callable, TypeVar, overload

T = TypeVar("T", bound=Callable[[], object])


@dataclass(frozen=True)
class TestCase:
    """A named, zero-argument test case."""

    name: str
    function: Callable[[], object]
    skip_reason: str | None = None
    tags: frozenset[str] = frozenset()


class AssertionFailure(AssertionError):
    """An expectation failure with values and its call site."""

    def __init__(
        self,
        message: str,
        *,
        expected: object = None,
        actual: object = None,
        has_values: bool = False,
        filename: str,
        line: int,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.expected = expected
        self.actual = actual
        self.has_values = has_values
        self.filename = filename
        self.line = line


@overload
def test(
    function: T,
    *,
    name: str | None = None,
    skip_reason: str | None = None,
    tags: Iterable[str] = (),
) -> TestCase: ...


@overload
def test(
    *,
    name: str | None = None,
    skip_reason: str | None = None,
    tags: Iterable[str] = (),
) -> Callable[[T], TestCase]: ...


def test(
    function: T | None = None,
    *,
    name: str | None = None,
    skip_reason: str | None = None,
    tags: Iterable[str] = (),
) -> TestCase | Callable[[T], TestCase]:
    """Declare a function as a named test case.

    The function must take no arguments. Use the returned ``TestCase`` with
    :func:`puffintest.run_tests`. Set ``name`` to choose the displayed name,
    or ``skip_reason`` to report the case as skipped without calling it.
    """
    normalized_tags = _normalize_tags(tags)

    def decorate(target: T) -> TestCase:
        display_name = (
            name if name is not None else target.__name__.replace("_", " ")
        )
        return TestCase(display_name, target, skip_reason, normalized_tags)

    if function is None:
        return decorate
    return decorate(function)


def test_cases(
    argument_sets: Iterable[tuple[object, ...]],
    *,
    name: str | None = None,
    tags: Iterable[str] = (),
) -> Callable[[Callable[..., object]], tuple[TestCase, ...]]:
    """Build one named test case for each positional argument tuple.

    The decorated function is called once per argument tuple. Each generated
    case includes its one-based index and arguments in its displayed name.
    """
    def decorate(function: Callable[..., object]) -> tuple[TestCase, ...]:
        normalized_tags = _normalize_tags(tags)
        base_name = (
            name if name is not None else function.__name__.replace("_", " ")
        )
        generated = []
        for index, arguments in enumerate(argument_sets, start=1):
            case_name = f"{base_name} [case {index}: {arguments!r}]"

            def invoke(arguments: tuple[object, ...] = arguments) -> object:
                return function(*arguments)

            generated.append(TestCase(case_name, invoke, tags=normalized_tags))
        return tuple(generated)

    return decorate


def _normalize_tags(tags: Iterable[str]) -> frozenset[str]:
    if isinstance(tags, str):
        raise TypeError("tags must be an iterable of tag names, not a string")
    values = tuple(tags)
    if any(not isinstance(tag, str) or not tag.strip() for tag in values):
        raise ValueError("tags must contain nonempty strings")
    return frozenset(tag.strip() for tag in values)


def _raise_failure(
    message: str,
    *,
    expected: object = None,
    actual: object = None,
    has_values: bool = False,
) -> None:
    frame = inspect.currentframe()
    helper = frame.f_back if frame is not None else None
    caller = helper.f_back if helper is not None else None
    if caller is None:  # pragma: no cover - defensive fallback for unusual runtimes
        filename, line = "<unknown>", 0
    else:
        filename, line = caller.f_code.co_filename, caller.f_lineno
    raise AssertionFailure(
        message,
        expected=expected,
        actual=actual,
        has_values=has_values,
        filename=filename,
        line=line,
    )


def expect_equal(actual: object, expected: object, message: str | None = None) -> None:
    """Fail unless ``actual`` equals ``expected``."""
    if actual != expected:
        _raise_failure(
            message or "Values are not equal",
            expected=expected,
            actual=actual,
            has_values=True,
        )


def expect_not_equal(actual: object, unexpected: object, message: str | None = None) -> None:
    """Fail unless ``actual`` differs from ``unexpected``."""
    if actual == unexpected:
        _raise_failure(
            message or "Values are unexpectedly equal",
            expected=f"a value different from {unexpected!r}",
            actual=actual,
            has_values=True,
        )


def expect_close(
    actual: float,
    expected: float,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 0.0,
    message: str | None = None,
) -> None:
    """Fail unless two numbers are close within the given tolerances.

    Uses :func:`math.isclose` semantics. ``rel_tol`` sets the relative
    tolerance; ``abs_tol`` is useful when comparing values near zero.
    """
    if not math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
        _raise_failure(
            message or f"Values are not close (rel_tol={rel_tol}, abs_tol={abs_tol})",
            expected=expected,
            actual=actual,
            has_values=True,
        )


def expect_not_close(
    actual: float,
    expected: float,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 0.0,
    message: str | None = None,
) -> None:
    """Fail if two numbers are close under :func:`math.isclose` semantics."""
    if math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
        _raise_failure(
            message or f"Values are unexpectedly close (rel_tol={rel_tol}, abs_tol={abs_tol})",
            expected=f"not close to {expected!r}",
            actual=actual,
            has_values=True,
        )


def expect_finite(actual: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is a finite number (not NaN or infinity)."""
    if not math.isfinite(actual):
        _raise_failure(message or "Value is not finite", expected="a finite number", actual=actual, has_values=True)


def expect_not_finite(actual: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is NaN or positive or negative infinity."""
    if math.isfinite(actual):
        _raise_failure(message or "Value is unexpectedly finite", expected="NaN or infinity", actual=actual, has_values=True)


def expect_nan(actual: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is NaN."""
    if not math.isnan(actual):
        _raise_failure(message or "Value is not NaN", expected="NaN", actual=actual, has_values=True)


def expect_not_nan(actual: float, message: str | None = None) -> None:
    """Fail if ``actual`` is NaN."""
    if math.isnan(actual):
        _raise_failure(message or "Value is unexpectedly NaN", expected="not NaN", actual=actual, has_values=True)


def expect_infinite(actual: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is positive or negative infinity."""
    if not math.isinf(actual):
        _raise_failure(message or "Value is not infinite", expected="positive or negative infinity", actual=actual, has_values=True)


def expect_not_infinite(actual: float, message: str | None = None) -> None:
    """Fail if ``actual`` is positive or negative infinity."""
    if math.isinf(actual):
        _raise_failure(message or "Value is unexpectedly infinite", expected="not infinity", actual=actual, has_values=True)


def expect_between(
    actual: float,
    minimum: float,
    maximum: float,
    message: str | None = None,
) -> None:
    """Fail unless ``actual`` is in the inclusive ``minimum`` to ``maximum`` range."""
    if not minimum <= maximum:
        raise ValueError("minimum must be less than or equal to maximum")
    if not minimum <= actual <= maximum:
        _raise_failure(
            message or "Value is outside the expected range",
            expected=f"between {minimum!r} and {maximum!r}, inclusive",
            actual=actual,
            has_values=True,
        )


def expect_not_between(
    actual: float,
    minimum: float,
    maximum: float,
    message: str | None = None,
) -> None:
    """Fail if ``actual`` is in the inclusive ``minimum`` to ``maximum`` range."""
    if not minimum <= maximum:
        raise ValueError("minimum must be less than or equal to maximum")
    if actual < minimum or actual > maximum:
        return
    _raise_failure(
        message or "Value is inside the unexpected range",
        expected=f"outside [{minimum!r}, {maximum!r}]",
        actual=actual,
        has_values=True,
    )


def expect_greater_than(actual: float, threshold: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is strictly greater than ``threshold``."""
    if not actual > threshold:
        _raise_failure(
            message or "Value is not greater than the threshold",
            expected=f"greater than {threshold!r}",
            actual=actual,
            has_values=True,
        )


def expect_less_than(actual: float, threshold: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is strictly less than ``threshold``."""
    if not actual < threshold:
        _raise_failure(
            message or "Value is not less than the threshold",
            expected=f"less than {threshold!r}",
            actual=actual,
            has_values=True,
        )


def expect_at_least(actual: float, threshold: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is greater than or equal to ``threshold``."""
    if not actual >= threshold:
        _raise_failure(
            message or "Value is below the minimum threshold",
            expected=f"at least {threshold!r}",
            actual=actual,
            has_values=True,
        )


def expect_at_most(actual: float, threshold: float, message: str | None = None) -> None:
    """Fail unless ``actual`` is less than or equal to ``threshold``."""
    if not actual <= threshold:
        _raise_failure(
            message or "Value is above the maximum threshold",
            expected=f"at most {threshold!r}",
            actual=actual,
            has_values=True,
        )


def expect_contains(container: object, item: object, message: str | None = None) -> None:
    """Fail unless ``item`` is present in ``container``."""
    try:
        contains_item = item in container  # type: ignore[operator]
    except TypeError as error:
        _raise_failure(
            message or f"Cannot check membership: {error}",
            expected=f"a container holding {item!r}",
            actual=container,
            has_values=True,
        )
    if not contains_item:
        _raise_failure(
            message or "Item is not present in the container",
            expected=f"a container holding {item!r}",
            actual=container,
            has_values=True,
        )


def expect_not_contains(container: object, item: object, message: str | None = None) -> None:
    """Fail unless ``item`` is absent from ``container``."""
    try:
        contains_item = item in container  # type: ignore[operator]
    except TypeError as error:
        _raise_failure(
            message or f"Cannot check membership: {error}",
            expected=f"a container not holding {item!r}",
            actual=container,
            has_values=True,
        )
    if contains_item:
        _raise_failure(
            message or "Item is unexpectedly present in the container",
            expected=f"a container not holding {item!r}",
            actual=container,
            has_values=True,
        )


def expect_matches(actual: str, pattern: str, message: str | None = None) -> None:
    """Fail unless ``pattern`` matches somewhere in ``actual``."""
    if not isinstance(actual, str):
        _raise_failure(
            message or "Expected a string to match the pattern",
            expected=f"text matching {pattern!r}",
            actual=actual,
            has_values=True,
        )
    if re.search(pattern, actual) is None:
        _raise_failure(
            message or "Text does not match the pattern",
            expected=f"text matching {pattern!r}",
            actual=actual,
            has_values=True,
        )


def expect_not_matches(actual: str, pattern: str, message: str | None = None) -> None:
    """Fail if ``pattern`` matches anywhere in ``actual``."""
    if not isinstance(actual, str):
        _raise_failure(
            message or "Expected a string not to match the pattern",
            expected=f"text not matching {pattern!r}",
            actual=actual,
            has_values=True,
        )
    if re.search(pattern, actual) is not None:
        _raise_failure(
            message or "Text unexpectedly matches the pattern",
            expected=f"text not matching {pattern!r}",
            actual=actual,
            has_values=True,
        )


def expect_starts_with(actual: str, prefix: str, message: str | None = None) -> None:
    """Fail unless ``actual`` starts with ``prefix``."""
    if not isinstance(actual, str) or not actual.startswith(prefix):
        _raise_failure(
            message or "Text does not start with the expected prefix",
            expected=f"text starting with {prefix!r}",
            actual=actual,
            has_values=True,
        )


def expect_ends_with(actual: str, suffix: str, message: str | None = None) -> None:
    """Fail unless ``actual`` ends with ``suffix``."""
    if not isinstance(actual, str) or not actual.endswith(suffix):
        _raise_failure(
            message or "Text does not end with the expected suffix",
            expected=f"text ending with {suffix!r}",
            actual=actual,
            has_values=True,
        )


def expect_not_starts_with(actual: str, prefix: str, message: str | None = None) -> None:
    """Fail if ``actual`` starts with ``prefix``."""
    if not isinstance(actual, str) or not isinstance(prefix, str):
        raise TypeError("actual and prefix must be strings")
    if actual.startswith(prefix):
        _raise_failure(message or "Text unexpectedly starts with the prefix", expected=f"text not starting with {prefix!r}", actual=actual, has_values=True)


def expect_not_ends_with(actual: str, suffix: str, message: str | None = None) -> None:
    """Fail if ``actual`` ends with ``suffix``."""
    if not isinstance(actual, str) or not isinstance(suffix, str):
        raise TypeError("actual and suffix must be strings")
    if actual.endswith(suffix):
        _raise_failure(message or "Text unexpectedly ends with the suffix", expected=f"text not ending with {suffix!r}", actual=actual, has_values=True)


def expect_length(actual: Sized, expected: int, message: str | None = None) -> None:
    """Fail unless ``actual`` has exactly ``expected`` items."""
    actual_length = len(actual)
    if actual_length != expected:
        _raise_failure(
            message or "Value has an unexpected length",
            expected=expected,
            actual=actual_length,
            has_values=True,
        )


def expect_length_between(
    actual: Sized, minimum: int, maximum: int, message: str | None = None
) -> None:
    """Fail unless ``actual`` has an inclusive number of items in the range."""
    if minimum < 0 or maximum < 0 or minimum > maximum:
        raise ValueError("length bounds must be nonnegative and ordered")
    actual_length = len(actual)
    if not minimum <= actual_length <= maximum:
        _raise_failure(
            message or "Value length is outside the expected range",
            expected=f"length between {minimum} and {maximum}, inclusive",
            actual=actual_length,
            has_values=True,
        )


def expect_empty(actual: Sized, message: str | None = None) -> None:
    """Fail unless ``actual`` contains no items."""
    expect_length(actual, 0, message or "Expected an empty value")


def expect_not_empty(actual: Sized, message: str | None = None) -> None:
    """Fail unless ``actual`` contains at least one item."""
    actual_length = len(actual)
    if actual_length == 0:
        _raise_failure(
            message or "Expected a non-empty value",
            expected="at least 1 item",
            actual=actual_length,
            has_values=True,
        )


def expect_is(actual: object, expected: object, message: str | None = None) -> None:
    """Fail unless ``actual`` and ``expected`` are the same object."""
    if actual is not expected:
        _raise_failure(
            message or "Values are not the same object",
            expected=expected,
            actual=actual,
            has_values=True,
        )


def expect_none(actual: object, message: str | None = None) -> None:
    """Fail unless ``actual`` is ``None``."""
    if actual is not None:
        _raise_failure(
            message or "Expected None",
            expected=None,
            actual=actual,
            has_values=True,
        )


def expect_not_none(actual: object, message: str | None = None) -> None:
    """Fail unless ``actual`` is not ``None``."""
    if actual is None:
        _raise_failure(
            message or "Expected a non-None value",
            expected="not None",
            actual=None,
            has_values=True,
        )


def expect_instance(
    actual: object, expected_type: type, message: str | None = None
) -> None:
    """Fail unless ``actual`` is an instance of ``expected_type``."""
    if not isinstance(actual, expected_type):
        _raise_failure(
            message or f"Expected an instance of {expected_type.__name__}",
            expected=expected_type,
            actual=actual,
            has_values=True,
        )


def expect_type(actual: object, expected_type: type, message: str | None = None) -> None:
    """Fail unless ``type(actual)`` is exactly ``expected_type``."""
    if type(actual) is not expected_type:
        _raise_failure(
            message or f"Expected exact type {expected_type.__name__}",
            expected=expected_type,
            actual=type(actual),
            has_values=True,
        )


def expect_true(actual: object, message: str | None = None) -> None:
    """Fail unless ``actual`` is truthy."""
    if not actual:
        _raise_failure(
            message or "Expected a truthy value",
            expected=True,
            actual=actual,
            has_values=True,
        )


def expect_false(actual: object, message: str | None = None) -> None:
    """Fail unless ``actual`` is falsey."""
    if actual:
        _raise_failure(
            message or "Expected a falsey value",
            expected=False,
            actual=actual,
            has_values=True,
        )


def fail(message: str = "Explicit failure") -> None:
    """Fail the current case with ``message``."""
    _raise_failure(message)


class _RaisesContext:
    def __init__(self, expected: type[Exception], message: str | None) -> None:
        self.expected = expected
        self.message = message
        self.exception: Exception | None = None

    def __enter__(self) -> _RaisesContext:
        return self

    async def __aenter__(self) -> _RaisesContext:
        return self

    def _handle_exception(self, exception_type: object, exception: object) -> bool:
        if exception_type is None:
            _raise_failure(
                self.message or f"Expected {self.expected.__name__} to be raised",
                expected=self.expected.__name__,
                actual="no exception",
                has_values=True,
            )
        if isinstance(exception, self.expected):
            self.exception = exception
            return True
        if isinstance(exception, Exception):
            _raise_failure(
                self.message or f"Expected {self.expected.__name__}, got {type(exception).__name__}",
                expected=self.expected.__name__,
                actual=type(exception).__name__,
                has_values=True,
            )
        return False

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> bool:
        return self._handle_exception(exception_type, exception)

    async def __aexit__(
        self, exception_type: object, exception: object, traceback: object
    ) -> bool:
        return self._handle_exception(exception_type, exception)


def expect_raises(
    exception_type: type[Exception], message: str | None = None
) -> _RaisesContext:
    """Return a context manager that requires ``exception_type`` to be raised.

    Works with both ``with`` and ``async with``. A matching exception is
    suppressed and made available as ``context.exception``. An unexpected
    exception becomes a failed expectation; process-control exceptions such
    as ``KeyboardInterrupt`` continue to propagate.
    """
    if not isinstance(exception_type, type) or not issubclass(exception_type, Exception):
        raise TypeError("exception_type must be an Exception subclass")
    return _RaisesContext(exception_type, message)


def expect_error_message(
    error: BaseException, substring: str, message: str | None = None
) -> None:
    """Fail unless ``substring`` occurs in ``str(error)``."""
    if not isinstance(error, BaseException):
        raise TypeError("error must be an exception")
    if not isinstance(substring, str):
        raise TypeError("substring must be a string")
    actual = str(error)
    if substring not in actual:
        _raise_failure(
            message or "Error message does not contain the expected text",
            expected=f"error message containing {substring!r}",
            actual=actual,
            has_values=True,
        )
