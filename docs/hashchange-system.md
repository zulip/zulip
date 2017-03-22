# URL hashes and deep linking

## Hashchange

The Zulip web application has a nice system of hash (#) URLs that can
be used to deep-link into the application and allow the browser's
"back" functionality to let you navigate between parts of the UI.
Some examples are:

* `/#settings/your-bots`: Bots section of the settings overlay.
* `/#streams`: Streams overlay
* `/#streams/15/streamName`: Streams overlay with stream ID 15 (called
  "streamName") selected.
* `/#narrow/stream/android/subject/fun`: Message feed showing stream
  "android" and topic "fun".

The main module in the frontend that manages this all is
`static/js/hashchange.js` (plus `hash_util.js` for all the parsing
code), which is unfortunately one of our thorniest modules.  Part of
the reason that it's thorny is that it needs to support a lot of
different flows:

* The user clicking on an in-app link, which in turn opens the Streams
  overlay.  This makes it easy to have simple links around the app
  without custom click handlers for each one.
* The user uses the "back" button in their browser (basically
  equivalent to the previous one).
* The user clicking some in-app click handler, that potentially does
  several UI-manipulating things including e.g. loading the streams
  overlay, and needs to update the hash without re-triggering the open
  animation (etc.).
* Within an overlay like the Streams overlay, the user clicks to
  another part of the overlay, which should update the hash but not
  re-trigger loading the overlay (which would result in a confusing
  animation experience).
* The user is in a part of the webapp, and reloads their browser window.
  Ideally the reloaded browser window should return them to their
  original state.
* A server-initiated browser reload (done after a new version is
  deployed, see notes below), where we try to preserve extra state
  (e.g. content of compose box, scroll position within a narrow)
  using the `/#reload` hash prefix.

When making changes to the hashchange system, it is absolutely
essential to test all of these flows, since we don't have great
automated tests for all of this (would be a good project to add them
to the Casper suite) and there's enough complexity that it's easy to
accidentally break something.

Here's some notes on how we handle these cases:

* `hashchange.hashchanged` is the function used to handle the hash in
  the browser changing with an open window (e.g. clicking on a link to
  a hash or using the back button).
* `hashchange.should_ignore` is the function `hashchange.hashchanged`
  calls to make it possible for clicking on links within a given
  overlay to just be managed by code within that overlay, without
  reloading the overlay.  It primarily checks whether the "main hash"
  (i.e. the first piece like `settings`) is in an overlay.
* `hashchange.do_hashchange` is what is called when you reload the
  browser.  If the hash is nonempty, it ensures the relevant overlay
  is opened or the user is narrowed as part of the page load process.
  It is also is called by `hashchange.hashchanged` when the hash
  changes outside the `should_ignore` boundaries, since the logic for
  that case is identical.
* `reload.preserve_state` is called when a server-initiated browser
  reload happens, and encodes a bunch of data like the current scroll
  position into the hash.
* `reload.initialize` handles restoring the preserved state after a
  reload where the hash starts with `/#reload`.

## Server-initiated reloads

There are a few circumstances when the Zulip browser window needs to
reload itself:

* If the browser has been offline for more than 10 minutes, the
  browser's [event queue](events-system.html) will have been
  garbage-collected by the server, meaning the browser can no longer
  getting real-time updates altogether.  In this case, the browser
  auto-reloads immediately in order to.  We have code an unsuspend
  trigger (based on some clever time logic) that ensures we check
  immediately when a client unsuspends; grep for `unsuspend` to see
  the code.
* If a new version of the server has been deployed, we want to reload
  the browser so that it will start running the latest code.  However,
  we don't want server deploys to be disruptive.  So, the backend
  preserves your event queues (etc.) and just pushes a special
  `restart` event to all clients.  That event causes the browser to
  start looking for a good time to reload, based on when the user is
  idle (ideally, we'd reload when they're not looking and restore
  state so that the user never knew it happened!).  The logic for
  doing this is in `static/js/reload.js`; but regardless we'll reload
  within 30 minutes unconditionally.

  An important detail in server-initiated reloads is that we
  desynchronize when browsers start attempting to them randomly, in
  order to avoid a thundering herd situation bringing down the server.

## All reloads

In addition to saving state as described above when reloading the
browser, Zulip also does a few bookkeeping things on page reload (like
cleaning up its event queue, and saving any text in an open compose
box as a draft).
