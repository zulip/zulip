---
paths:
  - "**/*.py"
---

# Python Code

- Don't use `Any` type annotations without comments justifying it.
- Don't use `cursor.execute()` with string formatting (SQL injection risk)
- Don't use `.extra()` in Django without careful review and commenting
- Don't create N+1 query patterns:

  ```python
  # BAD
  for bar in bars:
      foo = Foo.objects.get(id=bar.foo_id)

  # GOOD
  foos = {f.id: f for f in Foo.objects.filter(id__in=[b.foo_id for b in bars])}
  ```
