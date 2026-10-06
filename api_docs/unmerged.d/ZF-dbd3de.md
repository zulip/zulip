* [`GET /calls/bigbluebutton/create`](/api/create-big-blue-button-video-call),
  [`POST /calls/nextcloud_talk/create`](/api/create-nextcloud-talk-video-call),
  [`POST /calls/webex/create`](/api/create-webex-video-call),
  [`POST /calls/constructorgroups/create`](/api/create-constructor-groups-video-call):
  These endpoints now return an error if the realm has not selected
  the matching video call provider in its `video_chat_provider`
  setting.
