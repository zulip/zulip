from typing import Any

from django.db import connection
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Verify every miatsuco_* migration's dependency on zerver names
the actual current tip of zerver's own migration graph, not some ancestor left
over from an earlier rebase. See docs/contributing/miatsuco-fork-conventions.md
for the full rationale."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        # Local import: MigrationLoader pulls in the full app registry,
        # not needed for most management commands, so keep it out of
        # the module-level import cost for commands that never run this.
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        graph = loader.graph

        zerver_keys = [key for key in graph.nodes if key[0] == "zerver"]
        miatsuco_keys = {key for key in zerver_keys if key[1].startswith("miatsuco_")}
        upstream_keys = set(zerver_keys) - miatsuco_keys

        if not miatsuco_keys:
            self.stdout.write("No miatsuco_* migrations found; nothing to check.")
            return

        # A tip is an upstream node nothing else *upstream* depends on.
        # We deliberately only look at upstream-to-upstream edges here:
        # if we instead asked "does anything at all depend on this
        # node", every legitimate tip would incorrectly disqualify
        # itself the moment a miatsuco_* migration correctly depends on
        # it.
        depended_on: set[tuple[str, str]] = set()
        for key in upstream_keys:
            for parent in graph.node_map[key].parents:
                if parent in upstream_keys:
                    depended_on.add(parent)
        tips = upstream_keys - depended_on

        if len(tips) != 1:
            self.stdout.write(
                "Could not determine a single current tip for zerver's own "
                f"migration graph; found {len(tips)} candidate(s): "
                f"{sorted(key[1] for key in tips)}. This usually means "
                "zerver itself is in a multi-head state, which is an "
                "upstream-level problem to resolve first."
            )
            raise SystemExit(1)

        tip_name = next(iter(tips))[1]
        violations = []
        for key in sorted(miatsuco_keys):
            node = graph.node_map[key]
            zerver_parents = [p[1] for p in node.parents if p[0] == "zerver"]
            miatsuco_parents = [p for p in zerver_parents if p.startswith("miatsuco_")]
            non_miatsuco_zerver_parents = [
                p for p in zerver_parents if not p.startswith("miatsuco_")
            ]

            if not non_miatsuco_zerver_parents:
                # No direct dependency on an upstream zerver migration:
                # fine if this migration instead chains onto another
                # miatsuco_* migration (an internal chain within one
                # feature only needs its root to touch the upstream
                # graph).
                if miatsuco_parents:
                    continue
                violations.append(
                    f"{key[1]}: has no dependency on an upstream zerver "
                    "migration and doesn't chain onto another miatsuco_* "
                    "migration either -- check it by hand."
                )
                continue

            violations.extend(
                f"{key[1]}: depends on zerver migration "
                f"'{parent_name}', but the current actual tip is "
                f"'{tip_name}'. Update this migration's "
                "dependencies tuple to point at the tip -- do not "
                "rename the file itself (see "
                "docs/contributing/miatsuco-fork-conventions.md)."
                for parent_name in non_miatsuco_zerver_parents
                if parent_name != tip_name
            )

        if violations:
            self.stdout.write("miatsuco migration convention violations found:\n")
            for v in violations:
                self.stdout.write(f"  - {v}")
            self.stdout.write(f"\nCurrent zerver tip: {tip_name}")
            raise SystemExit(1)

        self.stdout.write(
            f"OK: {len(miatsuco_keys)} miatsuco_* migration(s) correctly chained onto zerver tip '{tip_name}'."
        )
