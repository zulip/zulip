# Multi-Channel Search: Implementation Notes

## Summary

This branch enforces canonical single-channel vs multi-channel behavior:

- Single channel:
  - Operator: `channel`
  - URL: `/#narrow/channel/<id>-<slug>`
  - Dedicated channel header is shown.
- Multiple channels:
  - Operator: `channels`
  - URL: `/#narrow/channels/<id1,id2,...>`
  - Dedicated single-channel header is not shown.

## Core Implementation

### Routing and canonicalization

- `web/src/hash_util.ts`
  - Canonicalizes legacy comma-`channel` and single-`channels` forms.
  - Prevents malformed canonical output for invalid operands.
- `web/src/hashchange.ts`
  - Redirects only canonicalizable channel/operator transitions.

### Narrow term behavior

- `web/src/filter.ts`
  - Validates `channels:<id,id,...>` terms strictly (numeric, unique, length >= 2).
  - Handles local predicate behavior for multi-channel terms.
- `web/src/narrow_state.ts`
  - Distinguishes single-channel (`stream_id`) from multi-channel (`stream_ids`) state.
- `web/src/message_view_header.ts`
  - Avoids single-channel header path for multi-channel-style operands.

### Search UI and suggestions

- `web/src/search_pill.ts`
  - Implements grouped channel pill state.
  - Normalizes and validates channel ID operands.
  - Automatically downgrades pill operator to `channel` when one channel remains.
- `web/src/search_suggestion.ts`
  - Adds grouped channel suggestion flow (`channel -> channels`).
  - Uses parsed term logic for channel-group suggestion replacement.
- `web/templates/search_channel_pill.hbs`
- `web/templates/search_list_item.hbs`
- `web/styles/search.css`

### Backend validation and query behavior

- `zerver/lib/narrow.py`
  - Enforces channel-category exclusivity:
    - no `channel` + `channels` mix
    - only one positive `channel`
    - only one positive `channels`
  - Strictly validates `channels:<id,id,...>` operands:
    - numeric IDs only
    - no empty tokens
    - no duplicates
    - no unknown/inaccessible IDs
  - Uses fail-fast web-public checks for channels ID lists.
  - Updates history-inclusion logic for channels ID-list narrows.

## Tests Updated

- `zerver/tests/test_message_fetch.py`
- `web/tests/hash_util.test.cjs`
- `web/tests/filter.test.cjs`
- `web/tests/search.test.cjs`
- `web/tests/search_suggestion.test.cjs`

## Why These Changes Were Needed

- Remove duplicate representations for the same single-channel state.
- Make channel category behavior canonical and mutually exclusive.
- Eliminate permissive malformed `channels` operand handling.
- Keep UI/operator/URL/backend state transitions consistent.
