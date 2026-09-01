---
paths:
  - "web/**/*.{js,cjs,mjs,ts,cts,mts}"
  - "web/**/*.hbs"
---

# Frontend Code

- JavaScript/TypeScript code must use `const` or `let`, never `var`.
- Avoid lodash in favor of modern ECMAScript primitives where available,
  keeping in mind our browserlist.
- Don't use `onclick` attributes in HTML; use event delegation
- Don't access DOM APIs (`document.documentElement.style`, `$()`
  selectors for specific elements) without guarding for node test
  environments, where the DOM is mocked minimally. Check that the
  element exists before using it.
