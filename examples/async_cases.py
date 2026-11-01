import asyncio
import sys

from puffintest import discover_tests, expect_equal, run_async_tests, test


async def load_value():
    await asyncio.sleep(0)
    return 42


@test
async def async_case_checks_loaded_value():
    expect_equal(await load_value(), 42)


async def main():
    return await run_async_tests(
        discover_tests(sys.modules[__name__]), case_timeout=5.0
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
