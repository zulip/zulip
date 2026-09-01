---
paths:
  - "web/**"
  - "templates/**"
---

# Manual Testing for UI Changes

If a PR makes frontend changes, manually verify the affected UI. This
catches issues that automated tests miss. **Treat this checklist as
blocking, not advisory** — every applicable item must be verified
before the change is ready.

## Visual appearance

- Is the new UI consistent with similar elements (fonts, colors, sizes)?
  Find the closest existing analogues and compare carefully.
- Is alignment correct, both vertically and horizontally? Measure
  programmatically with `getBoundingClientRect()` when in doubt —
  don't eyeball it.
- Do clickable elements have hover behavior consistent with similar UI?
- If elements can be disabled, does the disabled state look right?
- Did the change accidentally affect other parts of the UI? Use
  `git grep` to check if modified CSS is used elsewhere. CSS changes
  are notorious for unintended consequences — check every page and
  component that shares the selectors you modified.
- Check all of the above in both light and dark themes when the
  change could plausibly affect colors, contrast, or theme-dependent
  imagery. Pure geometry/typography changes (`font-size`,
  `line-height`, `margin`, `padding`, `display`, `font-weight`,
  etc.) don't need a separate dark-theme pass —
  `web/styles/dark_theme.css` only overrides colors, so a single
  theme suffices for theme-invariant changes.

## Responsiveness and internationalization

- Does the UI look good at different window sizes? Check wide desktop
  (1920px), typical laptop (1280px), tablet, and narrow phone (480px).
- Would the UI break if translated strings were 1.5x longer than
  English? What if they were half as long? Both directions matter.

## Functionality

- Are live updates working as expected?
- Is keyboard navigation, including tabbing to interactive elements, working?
- If the feature affects the message view, try different narrows: topic,
  channel, Combined feed, direct messages.
- If the feature affects the compose box, test both channel messages and
  direct messages, and both ways of resizing.
- If the feature requires elevated permissions, test as both a user who
  has permissions and one who does not.
- Think about feature interactions: could banners overlap? What about
  resolved/unresolved topics? Collapsed or muted messages?
- Think about edge cases in data: empty lists, very long names, single
  items vs. hundreds, special characters in strings.
