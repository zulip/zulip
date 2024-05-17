# URL hashes and deep linking

## Hashchange

The Zulip web application has a nice system of hash (#) URLs that can
be used to deep-link into the application and allow the browser's
"back" functionality to let the user navigate between parts of the UI.
Some examples are:

- `/#settings/your-bots`: Bots section of the settings overlay.
- `/#channels`: Streams overlay, where the user manages streams
  (subscription etc.)
- `/#channels/11/announce`: Streams overlay with stream ID 11 (called
  "announce") selected.
- `/#narrow/stream/42-android/topic/fun`: Message feed showing stream
  "android" and topic "fun". (The `42` represents the id of the
  stream.)

The main module in the frontend that manages this all is
`web/src/hashchange.js` (plus `hash_util.js` for all the parsing
code), which is unfortunately one of our thorniest modules. Part of
the reason that it's thorny is that it needs to support a lot of
different flows:

- The user clicking on an in-app link, which in turn opens an overlay.
  For example the streams overlay opens when the user clicks the small
  cog symbol on the left sidebar, which is in fact a link to
  `/#channels`. This makes it easy to have simple links around the app
  without custom click handlers for each one.
- The user uses the "back" button in their browser (basically
  equivalent to the previous one, as a _link_ out of the browser history
  will be visited).
- The user clicking some in-app click handler (e.g. "Stream settings"
  for an individual stream), that potentially does
  several UI-manipulating things including e.g. loading the streams
  overlay, and needs to update the hash without re-triggering the open
  animation (etc.).
- Within an overlay like the streams overlay, the user clicks to
  another part of the overlay, which should update the hash but not
  re-trigger loading the overlay (which would result in a confusing
  animation experience).
- The user is in a part of the web app, and reloads their browser window.
  Ideally the reloaded browser window should return them to their
  original state.
- A server-initiated browser reload (done after a new version is
  deployed, or when a user comes back after being idle for a while,
  see [notes below][self-server-reloads]), where we try to preserve
  extra state (e.g. content of compose box, scroll position within a
  narrow) using the `/#reload` hash prefix.

When making changes to the hashchange system, it is **essential** to
test all of these flows, since we don't have great automated tests for
all of this (would be a good project to add them to the
[Puppeteer suite][testing-with-puppeteer]) and there's enough complexity
that it's easy to accidentally break something.

The main external API lives in `web/src/browser_history.js`:

- `browser_history.update` is used to update the browser
  history, and it should be called when the app code is taking care
  of updating the UI directly
- `browser_history.go_to_location` is used when you want the `hashchange`
  module to actually dispatch building the next page

Internally you have these functions:

- `hashchange.hashchanged` is the function used to handle the hash,
  whether it's changed by the browser (e.g. by clicking on a link to
  a hash or using the back button) or triggered internally.
- `hashchange.do_hashchange_normal` handles most cases, like loading the main
  page (but maybe with a specific URL if you are narrowed to a
  stream or topic or direct messages, etc.).
- `hashchange.do_hashchange_overlay` handles overlay cases. Overlays have
  some minor complexity related to remembering the page from
  which the overlay was launched, as well as optimizing in-page
  transitions (i.e. don't close/re-open the overlay if you can
  easily avoid it).

## Server-initiated reloads

There are a few circumstances when the Zulip browser window needs to
reload itself:

- If the browser has been offline for more than 10 minutes, the
  browser's [event queue][events-system] will have been
  garbage-collected by the server, meaning the browser can no longer
  get real-time updates altogether. In this case, the browser
  auto-reloads immediately in order to reconnect. We have coded an
  unsuspend callback (based on some clever time logic) that ensures we
  check immediately when a client unsuspends; grep for `watchdog` to
  see the code.
- If a new version of the server has been deployed, we want to reload
  the browser so that it will start running the latest code. However,
  we don't want server deploys to be disruptive. So, the backend
  preserves user-side event queues (etc.) and just pushes a special
  `restart` event to all clients. That event causes the browser to
  start looking for a good time to reload, based on when the user is
  idle (ideally, we'd reload when they're not looking and restore
  state so that the user never knew it happened!). The logic for
  doing this is in `web/src/reload.js`; but regardless we'll reload
  within 30 minutes unconditionally.

  An important detail in server-initiated reloads is that we
  desynchronize when browsers start attempting them randomly, in
  order to avoid a thundering herd situation bringing down the server.

Here are some key functions in the reload system:

- `reload.preserve_state` is called when a server-initiated browser
  reload happens, and encodes a bunch of data like the current scroll
  position into the hash.
- `reload_setup.initialize` handles restoring the preserved state after a
  reload where the hash starts with `/#reload`.

## All reloads

In addition to saving state as described above when reloading the
browser, Zulip also does a few bookkeeping things on page reload (like
cleaning up its event queue, and saving any text in an open compose
box as a draft).

[testing-with-puppeteer]: ../testing/testing-with-puppeteer.md
[self-server-reloads]: #server-initiated-reloads
[events-system]: events-system.md
