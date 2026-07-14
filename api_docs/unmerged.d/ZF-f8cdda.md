* [`GET /messages`](/api/get-messages),
  [`GET /messages/matches_narrow`](/api/check-messages-match-narrow),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow),
  [`POST /register`](/api/register-queue):
    Added support for a new [search/narrow filter](/api/construct-narrow#changes)
  operator, `dm-with`, which replaces and deprecates the `dm-including`
  operator.
