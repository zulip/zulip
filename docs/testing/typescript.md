# TypeScript static types

Zulip is early in the process of migrating our codebase to use
[TypeScript](https://www.typescriptlang.org/), the leading static type
system for JavaScript. It works as an extension of the ES6 JavaScript
standard, and provides similar benefits to our use of
[the mypy static type system for Python](mypy.md).

We expect to eventually migrate the entire JavaScript codebase to
TypeScript, though our current focus is on getting the tooling and
migration process right, not on actually migrating the codebase.

As a result, the details in this document are preliminary ideas for
discussion and very much subject to change.

A typical piece of TypeScript code looks like this:

```ts
setdefault(key: K, value: V): V {
    const mapping = this._items[this._munge(key)];
    if (mapping === undefined) {
        return this.set(key, value);
    }
    return mapping.v;
}
```

The following resources are valuable for learning TypeScript:

- The main documentation on [TypeScript syntax][typescript-handbook].

## Type checking

TypeScript types are checked by the TypeScript compiler, `tsc`, which
is run as part of our [lint checks](linters.md). You can run the
compiler yourself with `tools/run-tsc`, which will check all the
TypeScript files once, or `tools/run-tsc --watch`, which will
continually recheck the files as you edit them.

## Linting and style

We use the ESLint plugin for TypeScript to lint TypeScript code, just
like we do for JavaScript. Our long-term goal is to use an idiomatic
TypeScript style for our TypeScript codebase.

However, because we are migrating an established JavaScript codebase,
we plan to start with a style that is closer to the existing
JavaScript code, so that we can easily migrate individual modules
without too much code churn. A few examples:

- TypeScript generally prefers explicit `return undefined;`, whereas
  our existing JavaScript style uses just `return;`.
- With TypeScript, we expect to make heavy use of `let` and `const`
  rather than `var`.
- With TypeScript/ES6, we may no longer need to use `_.each()` as our
  recommended way to do loop iteration.

For each of the details, we will either want to bulk-migrate the
existing JavaScript codebase before the migration or plan to do it
after JS->TS migration for a given file, so that we don't need to
modify these details as part of converting a file from JavaScript to
TypeScript.

A possibly useful technique for this will be setting some eslint
override rules at the top of individual files in the first commit that
converts them from JS to TS.

## Migration strategy

Our plan is to order which modules we migrate carefully, starting with
those that:

- Appear frequently as reverse dependencies of other modules
  (e.g., `people.js`). These are most valuable to do first because
  then we have types on the data being interacted with by other
  modules when we migrate those.
- Don't have large open pull requests (to avoid merge conflicts); one
  can scan for these using [TinglingGit](https://github.com/zulip/TinglingGit).
- Have good unit test coverage, which limits the risk of breaking
  correctness through refactoring. Use
  `tools/test-js-with-node --coverage` to get a coverage report.

When migrating a module, we want to be especially thoughtful about
putting together a commit structure that makes mistakes unlikely and
the changes easy to verify. For example:

- First a commit that just converts the language to TypeScript adding
  types. The result may potentially have some violations of the
  long-term style we want (e.g., not using `const`). Depending on how
  we're handling linting, we set some override eslint rules at the top
  of the module at this stage so CI still passes.
- Then a commit just migrating use of `var` to `const/let` without
  other changes (other than removing any relevant linter overrides).
- Etc.

With this approach, we should be able to produce a bunch of really
simple commits that can be merged the same day they're written without
significant risk of introducing regressions from typos, refactors that
don't quite work how they were expected to, etc.

[typescript-handbook]: https://www.typescriptlang.org/docs/handbook/basic-types.html
