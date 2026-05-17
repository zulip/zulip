* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  and [`GET /realm/profile_fields`](/api/get-custom-profile-fields): Added
  `rendered_name` and `rendered_hint` fields to `CustomProfileField`
  objects. These fields contain the `name` and `hint` of the custom profile
  field rendered as HTML. Only inline formatting is rendered (bold, italic,
  code, links, strikethrough); block elements such as headings and lists,
  along with entity references such as user mentions, channel links,
  timestamps, emoji, and math, are stripped to plain text.
