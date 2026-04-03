* `PATCH /bots/{bot_user_id}`, `POST /bots/{bot_user_id}`:
  Added `service_triggers` parameter for specifying and
  changing a service bot's [triggers](/help/bots-overview#outgoing-webhook-bot-triggers).

* [`GET /events`](/api/get-events): Added a `triggers` array
  field to the `service` object for service bots. It specifies
  a service bot's [triggers](/help/bots-overview#outgoing-webhook-bot-triggers).
