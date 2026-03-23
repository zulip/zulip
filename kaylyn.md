# Kaylyn Frontend Handoff: Recurring Scheduler UI

## What I Implemented (Frontend Only)

I implemented a recurring scheduling UI inside Zulip's existing **Schedule message** popover.  
This is currently frontend-only; backend integration is marked TODO.

### 1. Recurring form controls
- Added section title: `Schedule recurring message (TODO)`.
- Added recurrence frequency selector: `Daily`, `Weekly`, `Monthly`.
- Added time selector.
- Added recurrence-specific custom fields:
  - `Weekly`: choose one or more days (`Mon` ... `Sun`).
  - `Monthly`: choose a day of month (`1..31`) or `Last day of month`.

### 2. Destination selection with native Zulip UI
- Added `Channels` picker using Zulip's stream pills + typeahead.
- Added `Direct messages` picker using Zulip's user pills + typeahead.
- Both support:
  - search as you type
  - selecting multiple items
  - consistent Zulip typography/components

### 3. Frontend validation behavior
- Validate button label: `Check Draft is Valid (must implement backend)`.
- Validation checks:
  - recurrence and time are selected
  - at least one destination exists (channel or DM)
  - weekly recurrence has at least one selected weekday
  - monthly recurrence has selected month day
- Inline status feedback shown in recurring builder.

### 4. UI polish + stability
- Tightened layout spacing and rounded controls.
- Updated validate button styling to a less saturated default palette tone.
- Kept popover compact/responsive.
- Added one-time init guard for recurring UI setup.
- Reinitializes recurring UI when send-later options rerender.
- Added click-outside handling to reduce accidental close behavior while interacting with typeaheads.

## Files Modified

- `web/templates/popovers/schedule_message_popover.hbs`
- `web/src/compose_send_menu_popover.ts`
- `web/styles/scheduled_messages.css`
- `web/src/pill_typeahead.ts` (optional config support added)

---

## Backend Contract (Proposed)

The frontend is ready to send/consume these shapes.

## 1) Create recurring scheduled message

**Endpoint**
- `POST /json/recurring_scheduled_messages`

**Request body**
```json
{
  "content": "message text",
  "recurrence": {
    "frequency": "daily",
    "time": "09:30",
    "timezone": "America/New_York",
    "weekly_days": [],
    "month_day": null
  },
  "destinations": {
    "stream_ids": [12, 34],
    "dm_user_ids": [5, 9]
  }
}
```

**Rules**
- `frequency` must be one of: `daily`, `weekly`, `monthly`.
- `time` format `HH:MM` (24-hour).
- `timezone` must be a valid IANA timezone.
- If `frequency=weekly`, `weekly_days` must be non-empty and values in: `MO,TU,WE,TH,FR,SA,SU`.
- If `frequency=monthly`, `month_day` must be `1..31` or `"last"`.
- Must have at least one destination (`stream_ids` or `dm_user_ids`).
- Validate all IDs belong to current realm and user has permission.

**Success response (example)**
```json
{
  "result": "success",
  "msg": "",
  "job": {
    "id": 101,
    "content": "message text",
    "recurrence": {
      "frequency": "weekly",
      "time": "09:30",
      "timezone": "America/New_York",
      "weekly_days": ["MO", "WE"],
      "month_day": null
    },
    "destinations": {
      "stream_ids": [12, 34],
      "dm_user_ids": [5, 9]
    },
    "next_delivery": "2026-03-10T13:30:00Z",
    "active": true
  }
}
```

## 2) List recurring scheduled messages

**Endpoint**
- `GET /json/recurring_scheduled_messages`

**Success response (example)**
```json
{
  "result": "success",
  "msg": "",
  "jobs": [
    {
      "id": 101,
      "content": "message text",
      "recurrence": {
        "frequency": "weekly",
        "time": "09:30",
        "timezone": "America/New_York",
        "weekly_days": ["MO", "WE"],
        "month_day": null
      },
      "destinations": {
        "stream_ids": [12, 34],
        "dm_user_ids": [5, 9]
      },
      "next_delivery": "2026-03-10T13:30:00Z",
      "active": true
    }
  ]
}
```

## 3) Cancel recurring scheduled message

**Endpoint**
- `DELETE /json/recurring_scheduled_messages/{id}`

**Success response**
```json
{
  "result": "success",
  "msg": ""
}
```

---

## Error Shape Recommendation

Use field-specific errors so frontend can map precisely:

```json
{
  "result": "error",
  "msg": "Invalid data",
  "errors": {
    "recurrence.frequency": "Must be daily, weekly, or monthly",
    "recurrence.weekly_days": "Pick at least one weekday",
    "recurrence.month_day": "Must be 1-31 or 'last'",
    "destinations": "At least one destination is required"
  }
}
```

---

## Backend Notes

- Compute `next_delivery` from recurrence in timezone-aware way.
- Handle DST transitions correctly.
- On each successful send, compute and persist next occurrence.
- Reuse Zulip message-sending pipeline for actual delivery.
- Add list/cancel permissions so users only manage their own recurring jobs (unless admin behavior is intentionally designed).
