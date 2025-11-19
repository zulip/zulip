If you ever see stale frontend behavior after changing branches, run:

```bash
pnpm install --force
pnpm rebuild
This forces pnpm to refresh the local installation and rebuild any native modules. Avoid manually copying `node_modules` between branches — always prefer the `pnpm` commands above. These steps clarify how Zulip refreshes frontend dependencies with the current pnpm workflow.

