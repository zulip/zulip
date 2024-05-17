The files in this subtree are part of the Zulip web frontend,
and are also incorporated by the Zulip mobile app.

Note that the deployment cycles are different:

- In the web app, this code is deployed in the same way as the rest of
  the web frontend: it's part of the server tree, and the browser
  gets it from the server, so the client is always running the same
  version the server just gave it.

- In the mobile app, this code is deployed in the same way as the
  rest of the mobile app: it's bundled up into the app binary which
  is uploaded to app stores and users install on their devices. The
  client will be running the version built into their version of the
  mobile app, which may be newer, older, or simply different from the
  version on the server.

  The mobile app always refers to a specific version of this code;
  changes to this code will appear in the mobile app only after a
  commit in the mobile app pulls them in.

To update the version of @zulip/shared on NPM, see the
[instructions][publishing-shared] in the mobile repo.

[publishing-shared]: https://github.com/zulip/zulip-mobile/blob/main/docs/howto/shared.md#publishing-zulipshared-to-npm
