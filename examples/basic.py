import sys

from puffintest import (
    expect_contains,
    expect_close,
    expect_finite,
    expect_nan,
    expect_not_nan,
    expect_infinite,
    expect_not_infinite,
    expect_equal,
    expect_instance,
    expect_empty,
    expect_error_message,
    expect_greater_than,
    expect_at_least,
    expect_at_most,
    expect_length_between,
    expect_not_empty,
    expect_not_close,
    expect_not_contains,
    expect_not_between,
    expect_less_than,
    expect_raises,
    expect_true,
    discover_tests,
    run_tests,
    test,
    test_cases,
)


@test(name="title formatting", tags=("text", "fast"))
def title_is_formatted():
    expect_equal("hello, puffin".title(), "Hello, Puffin")
    expect_contains("puffin test", "test")
    expect_not_contains("puffin test", "penguin")


@test
def empty_name_is_rejected():
    expect_true(not "   ".strip())


@test
def parser_reports_bad_input():
    with expect_raises(ValueError) as raised:
        int("not a number")
    expect_instance(raised.exception, ValueError)
    expect_contains(str(raised.exception), "invalid literal")
    expect_error_message(raised.exception, "invalid literal")


@test_cases([(0, 0), (1, 2), (-1, -2)], name="doubling", tags=("math", "fast"))
def doubling_matches(value, expected):
    expect_equal(value * 2, expected)


@test
def fractional_calculation_is_close():
    expect_finite(3.14)
    expect_nan(float("nan"))
    expect_not_nan(3.14)
    expect_infinite(float("inf"))
    expect_not_infinite(3.14)
    expect_greater_than(5, 3)
    expect_less_than(2, 3)
    expect_at_least(3, 3)
    expect_at_most(3, 3)
    expect_not_between(4, 1, 3)
    expect_not_close(0.1, 0.9)
    expect_close(0.1 + 0.2, 0.3, abs_tol=1e-12)
    expect_length_between(["puffin", "tern"], 1, 3)
    expect_empty([])
    expect_not_empty(["puffin"])


if __name__ == "__main__":
    raise SystemExit(run_tests(discover_tests(sys.modules[__name__])))
