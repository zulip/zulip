The `v2_*.json` files are the unmodified JSON examples from Honeybadger's
official webhook reference, retrieved on 2026-11-10:

https://docs.honeybadger.io/guides/integrations/payloads/v2/

Each fixture's source is `https://docs.honeybadger.io/guides/integrations/payloads/v2/EVENT.md`,
where `EVENT` is the fixture name without `v2_` or `.json`.

The existing `test_error.json`, `uptime.json`, and `checkin.json` fixtures
contain earlier recorded requests. They also verify compatibility with the
older form of the v2 payload.
