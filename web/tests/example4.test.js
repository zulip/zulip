"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

/*

    Let's step back and review what we've done so far.

    We've used fairly straightforward testing techniques
    to explore the following modules:

        filter
        message_store
        narrow_state
        people
        stream_data
        util

    We haven't gone deep on any of these objects, but if
    you are interested, all of these objects have test
    suites that have 100% line coverage on the modules
    that implement those objects.  For example, you can look
    at people.test.js in this directory for more tests on the
    people object.

    We can quickly review some testing concepts:

        zrequire - bring in real code
        mock_esm - mock es6 modules
        assert.equal - verify results

    ------

    Let's talk about our next steps.

    An app is pretty useless without an actual data source.
    One of the primary ways that a Zulip client gets data
    is through events.  (We also get data at page load, and
    we can also ask the server for data, but that's not in
    the scope of this conversation yet.)

    Chat systems are dynamic.  If an admin adds a user, or
    if a user sends a messages, the server immediately sends
    events to all clients so that they can reflect appropriate
    changes in their UI.  We're not going to discuss the entire
    "full stack" mechanism here.  Instead, we'll focus on
    the client code, starting at the boundary where we
    process events.

    Let's just get started...

*/

// We are going to use mock versions of some of our libraries.
const activity = mock_esm("../src/activity");
const message_live_update = mock_esm("../src/message_live_update");
const pm_list = mock_esm("../src/pm_list");
const settings_users = mock_esm("../src/settings_users");

// Use real versions of these modules.
const people = zrequire("people");
const server_events_dispatch = zrequire("server_events_dispatch");

const bob = {
    email: "bob@example.com",
    user_id: 33,
    full_name: "Bob Roberts",
    is_bot: true,
};

run_test("add users with event", ({override}) => {
    people.init();

    const event = {
        type: "realm_user",
        op: "add",
        person: bob,
    };

    assert.ok(!people.is_known_user_id(bob.user_id));

    // We need to override a stub here before dispatching the event.
    // Keep reading to see how overriding works!
    override(settings_users, "redraw_bots_list", () => {});
    // Let's simulate dispatching our event!
    server_events_dispatch.dispatch_normal_event(event);

    // And it works!
    assert.ok(people.is_known_user_id(bob.user_id));
});

/*

   It's actually a little surprising that adding a user does
   not have side effects beyond the people object and the bots list.
   I guess we don't immediately update the buddy list, but that's
   because the buddy list gets updated on the next server
   fetch.

   Let's try an update next.  To make this work, we will want
   to override some more of our stubs.

   This is where we see a little extra benefit from the
   run_test wrapper.  It passes us in an object that we
   can use to override data, and that works within the
   scope of the function.

*/

run_test("update user with event", ({override}) => {
    people.init();
    people.add_active_user(bob);

    const new_bob = {
        email: "bob@example.com",
        user_id: bob.user_id,
        full_name: "The Artist Formerly Known as Bob",
        is_bot: true,
    };

    const event = {
        type: "realm_user",
        op: "update",
        person: new_bob,
    };

    // We have to stub a few things. We don't want to test
    // the details of these functions, but we do want to
    // verify that they run. Fortunately, the run_test()
    // wrapper will tell us if we override a method that
    // doesn't get called!
    override(activity, "redraw", () => {});
    override(message_live_update, "update_user_full_name", () => {});
    override(pm_list, "update_private_messages", () => {});
    override(settings_users, "update_user_data", () => {});
    override(settings_users, "update_bot_data", () => {});

    // Dispatch the realm_user/update event, which will update
    // data structures and have other side effects that are
    // stubbed out above.
    server_events_dispatch.dispatch_normal_event(event);

    const user = people.get_by_user_id(bob.user_id);

    // Verify that the code actually did its main job:
    assert.equal(user.full_name, "The Artist Formerly Known as Bob");
});
