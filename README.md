# PuffinTest for Python

PuffinTest is an early Python test-case runner focused on short, readable failure reports. It currently provides named zero-argument cases, equality, truth, membership, and exception expectations, explicit failure, and a runner that continues with the next case after a failure.

This package is under development and has not been published to PyPI. The API and setup instructions may change.

## Requirements

Python 3.10 or newer.

## Install from this checkout

From the `python/` directory:

```sh
python3 -m pip install -e .
```

This installation exposes the `puffintest` command.

## Example

```python
from puffintest import expect_equal, run_tests, test


@test
def title_is_formatted():
    expect_equal("hello, puffin".title(), "Hello, Puffin")


if __name__ == "__main__":
    raise SystemExit(run_tests([title_is_formatted]))
```

Save this as `example.py` and run it with `python3 example.py` after installing the package. `run_tests` returns `0` when every case passes and `1` if any case fails, so `SystemExit` gives the process the matching exit status.

The repository includes a runnable [basic example](examples/basic.py). To see a failure report, change its expected title to a value that does not match.

## API

- `@test` turns a zero-argument function into a named `TestCase`. Its function name is displayed with underscores replaced by spaces; pass `name="..."` to choose a custom report name and `tags=("unit",)` to label it.
- `@test(skip_reason="...")` marks a case as skipped; its function is not called and the reason appears in the summary.
- `@test_cases(argument_sets, name=None, tags=())` creates one case per tuple of positional arguments. Each case name includes its index and argument values.
- `expect_equal(actual, expected, message=None)` checks equality.
- `expect_not_equal(actual, unexpected, message=None)` checks inequality.
- `expect_close(actual, expected, *, rel_tol=1e-9, abs_tol=0.0, message=None)` checks numeric values using `math.isclose` semantics.
- `expect_greater_than` and `expect_less_than` check strict thresholds; `expect_at_least` and `expect_at_most` accept equality at the threshold.
- `expect_between(actual, minimum, maximum, message=None)` checks an inclusive range. `expect_not_between(actual, minimum, maximum, message=None)` passes only when the value is outside that range. Both raise `ValueError` when bounds are reversed or unordered.
- `expect_contains(container, item, message=None)` checks membership.
- `expect_not_contains(container, item, message=None)` checks that an item is absent.
- `expect_length(actual, expected, message=None)` checks the length of a sized value; `expect_length_between(actual, minimum, maximum, message=None)` checks an inclusive range; `expect_empty` and `expect_not_empty` are shortcuts for zero and nonzero length.
- `expect_matches(actual, pattern, message=None)` and `expect_not_matches(actual, pattern, message=None)` check whether a regular expression occurs in a string. They use Python's `re.search` behavior.
- `expect_starts_with(actual, prefix, message=None)` and `expect_ends_with(actual, suffix, message=None)` check string prefixes and suffixes; `expect_not_starts_with` and `expect_not_ends_with` assert their absence.
- `expect_is(actual, expected, message=None)` checks object identity. `expect_none(actual, message=None)` and `expect_not_none(actual, message=None)` check for `None`.
- `expect_instance(actual, expected_type, message=None)` checks with `isinstance`; `expect_type(actual, expected_type, message=None)` checks the exact type.
- `expect_true(actual, message=None)` and `expect_false(actual, message=None)` check truthiness.
- `expect_error_message(error, substring, message=None)` checks a substring of `str(error)`.
- `expect_raises(ExceptionType, message=None)` is a context manager usable with `with` or `async with` for code expected to raise an exception. The matching exception is available as `context.exception`.
- `fail(message="Explicit failure")` fails the current case directly.
- `run_tests(cases, *, name_filter=None, tag_filter=None, fail_fast=False, before_each=None, after_each=None)` runs synchronous cases and hooks.
- `run_async_tests(cases, *, name_filter=None, tag_filter=None, fail_fast=False, before_each=None, after_each=None, case_timeout=None)` awaits async cases and hooks, and also supports synchronous callbacks.
- `discover_tests(module)` collects test cases declared in a module, including parameterized cases, in declaration order.

An expectation failure stops its current case. The runner then executes the remaining cases. Failure output includes the case, message, expected and actual values when available, and the source call site. Unexpected exceptions are reported by type and message with their last traceback location.

Skipped cases are reported separately and do not make the run fail. A run with no failures returns status `0`, even when it contains skipped cases. `name_filter` selects cases whose names contain the given text, ignoring case. `tag_filter` selects cases with that exact tag, also ignoring case. If the combined filters match no cases, the run returns `1`. Set `fail_fast=True` to stop after the first failed case; by default, all matching cases run.

Optional `before_each` and `after_each` callbacks run around each selected, non-skipped case. Teardown runs even if the case fails. If setup fails, that case is reported as failed and teardown is skipped. The async runner accepts either synchronous callbacks or awaitable callbacks.

```python
state = {}

def setup():
    state["items"] = []

def teardown():
    state.clear()

run_tests(discover_tests(sys.modules[__name__]), before_each=setup, after_each=teardown)
```

```python
run_tests([title_is_formatted], name_filter="title", fail_fast=True)
```

Parameterized cases:

```python
@test_cases([(0, 0), (1, 2), (-1, -2)], name="doubling")
def doubling_matches(value, expected):
    expect_equal(value * 2, expected)

run_tests(doubling_matches)
```

To discover every case declared in a module, pass the module object to `discover_tests`:

```python
import sys
from puffintest import discover_tests, run_tests

raise SystemExit(run_tests(discover_tests(sys.modules[__name__])))
```

For asynchronous cases, await the async runner inside an event loop:

```python
import asyncio
import sys
from puffintest import discover_tests, run_async_tests

async def main():
    return await run_async_tests(discover_tests(sys.modules[__name__]))

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

The repository includes a complete [async example](examples/async_cases.py). `case_timeout` limits each awaited test body and must be greater than zero. It does not limit synchronous test bodies or setup and teardown hooks. The synchronous runner reports an error if a case returns an awaitable, to avoid silently treating an unexecuted coroutine as a pass.

## Command line

Run one or more test files with the installed command:

```sh
puffintest examples/basic.py examples/async_cases.py
```

Use `--list` to inspect discovered cases without executing their test functions. Filter case names with `--filter text` or select tagged cases with `--tag unit`. Name and tag filters can be combined. Tags match exactly, ignoring case. Stop at the first failure with `--fail-fast`; use `--case-timeout 2.5` to limit each awaited test body. The command runs both synchronous and asynchronous cases and exits nonzero if a case fails, no cases are found, or a filter matches nothing.

For floating-point results, set an absolute tolerance when values may be near zero:

```python
expect_close(0.1 + 0.2, 0.3, abs_tol=1e-12)
expect_between(18, 13, 19)
```

Use regular-expression expectations to check text formats without comparing an entire string:

```python
from puffintest import expect_matches, expect_not_matches

expect_matches("order-4821 accepted", r"order-\d+ accepted")
expect_not_matches("request failed", r"\b2xx\b")
```

Check collection sizes directly, or use the empty and non-empty shortcuts:

```python
from puffintest import expect_empty, expect_length, expect_not_empty

expect_length(["alpha", "beta"], 2)
expect_empty([])
expect_not_empty({"user": "ada"})
```

Example:

```python
from puffintest import expect_contains, expect_raises

with expect_raises(ValueError) as raised:
    int("not a number")

expect_contains(str(raised.exception), "invalid literal")
```

`expect_raises` also works with `async with`, so it can check awaited operations:

```python
@test
async def missing_record_raises():
    async with expect_raises(LookupError) as raised:
        await load_record("missing")

    expect_contains(str(raised.exception), "missing")
```

## Development status

This is an initial implementation. Automated coverage, supported Python versions, and behavior on a clean installation still need verification before this page can be treated as stable package guidance.
