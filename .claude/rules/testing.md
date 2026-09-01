---
paths:
  - "zerver/tests/**"
  - "zerver/webhooks/**"
  - "web/tests/**"
---

# Testing Philosophy

- Write end-to-end tests when possible verifying what's important, not
  internal APIs.
- Tests must work offline. Use fixtures (in `zerver/tests/fixtures`) for
  external service testing and `responses` for simpler things.
- Use time_machine and similar libraries to mock time.
- Read `zerver/tests/test_example.py` for patterns.
- A good failing test before implementing is good practice so your
  test and code can jointly verify each other.
- Remember to always assert state is correctly updated, not just "success".
- In tests, don't assert on `assertLogs` output with
  `any(phrase in line for line in mock_log.output)`; pin the full line
  against `mock_log.output`, or a substring to a specific `mock_log.output[i]`.

A common failure mode is failing to have test coverage for error
conditions that require coverage (note `tools/coveragerc` excludes
asserts). Run `test-backend --coverage FooTest` and check the coverage
data to confirm that the new lines you added are in fact run by the
tests.

## For webhooks

```bash
./tools/test-backend zerver/webhooks/<integration>
```
