* [`GET /events`](/api/get-events): Added `rendered_description_version` field to the
  user group update event when the `description` property is changed.
* User group objects now include `rendered_description_version` field to track the
  markdown rendering version used for `rendered_description_html`.
