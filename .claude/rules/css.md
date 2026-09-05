---
paths:
  - "web/styles/**"
---

# Writing CSS

- Use `em` units instead of `px` for computed CSS values that need to
  scale with font size. Pixel approximations break at different zoom
  levels and font-size settings.
- **Review CSS for redundant rules.** After writing CSS, review the
  full set of rules affecting the same elements. Look for rules that
  are immediately overridden by a more specific selector, duplicated
  selector lists, or cases where scoping (e.g., `:not()`) would
  eliminate the need for an override.
- **Check CSS change scope.** When modifying CSS, always check what
  other pages or components use the same selectors, files, and
  classes. Use `git grep` on class names and check webpack bundle
  entries to understand which pages load the file. Prefer scoped
  overrides (e.g., `.parent .target`) over modifying shared rules,
  to avoid unintended changes to other parts of the app.
- Use class or ID selectors, not bare tag selectors or attribute
  selectors. If no suitable class exists, add one.

When removing a CSS dependency (e.g., Bootstrap), audit the full
property list of every rule, not just visually obvious properties like
colors and backgrounds. Subtle properties like `line-height`, `margin`,
`padding`, `text-decoration`, `font-weight`, and `border` are easy to
miss but cause visible regressions. Check inherited properties too —
e.g., a `body` rule's `line-height` or `margin` affects all descendants.
