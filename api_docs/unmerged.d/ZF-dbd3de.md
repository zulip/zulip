* [`GET /calls/bigbluebutton/create`](/api/create-big-blue-button-video-call),
  [`POST /calls/google_meet/create`](/api/create-google-meet-video-call),
  [`POST /calls/nextcloud_talk/create`](/api/create-nextcloud-talk-video-call),
  [`POST /calls/webex/create`](/api/create-webex-video-call),
  [`POST /calls/constructorgroups/create`](/api/create-constructor-groups-video-call),
  `POST /calls/zoom/create`:
  These endpoints now return an error if the organization has not
  configured the matching video call provider as its [video call
  provider](/help/configure-call-provider).
