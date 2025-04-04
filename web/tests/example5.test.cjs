"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

/*
   Our test from an earlier example verifies that the update events
   leads to a name change inside the people object, but it obviously
   kind of glosses over the other interactions.

   We can go a step further and verify the sequence of operations that
   happen during an event.  This concept is called "stubbing", and you
   can find libraries to help do stubbing.  Here we will just build our
   own lightweight stubbing system, which is almost trivially easy to
   do in a language like JavaScript.

*/

// First we tell the compiler to skip certain modules and just
// replace them with {}.
const direct_message_group_data = mock_esm("../src/direct_message_group_data");
const message_lists = mock_esm("../src/message_lists");
const message_notifications = mock_esm("../src/message_notifications");
const pm_list = mock_esm("../src/pm_list");
const stream_list = mock_esm("../src/stream_list");
const unread_ui = mock_esm("../src/unread_ui");
const activity = mock_esm("../src/activity");

let added_message = false;
message_lists.current = {
    data: {
        filter: {
            can_apply_locally() {
                return true;
            },
        },
    },
    add_messages() {
        added_message = true;
    },
};
message_lists.all_rendered_message_lists = () => [message_lists.current];
message_lists.non_rendered_data = () => [];

// And we will also test some real code, of course.
const message_events = zrequire("message_events");
const message_store = zrequire("message_store");
const people = zrequire("people");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

const isaac = make_user({
    email: "isaac@example.com",
    user_id: 30,
    full_name: "Isaac Newton",
});
people.add_active_user(isaac);

/*
   Next we create a test_helper that will allow us to redirect methods to an
   events array, and we can then later verify that the sequence of side effect
   is as predicted.

   (Note that for now we don't simulate return values nor do we inspect the
   arguments to these functions.  We could easily extend our helper to do more.)

   The forthcoming example is a pretty extreme example, where we are calling a
   pretty high level method that dispatches a lot of its work out to other
   objects.

*/

function test_helper({override}) {
    const events = [];

    return {
        redirect(module, func_name) {
            override(module, func_name, () => {
                events.push([module, func_name]);
            });
        },
        events,
    };
}

run_test("insert_message", ({override}) => {
    message_store.clear_for_testing();

    override(pm_list, "update_private_messages", noop);

    const helper = test_helper({override});

    const new_message = {
        sender_id: isaac.user_id,
        id: 1001,
        content: "example content",
        topic: "Foo",
        type: "stream",
    };

    assert.equal(message_store.get(new_message.id), undefined);

    helper.redirect(direct_message_group_data, "process_loaded_messages");
    helper.redirect(message_notifications, "received_messages");
    helper.redirect(stream_list, "update_streams_sidebar");
    helper.redirect(unread_ui, "update_unread_counts");
    helper.redirect(activity, "set_received_new_messages");

    message_events.insert_new_messages([new_message]);

    // Even though we have stubbed a *lot* of code, our
    // tests can still verify the main "narrative" of how
    // the code invokes various objects when a new message
    // comes in:
    assert.deepEqual(helper.events, [
        [direct_message_group_data, "process_loaded_messages"],
        [unread_ui, "update_unread_counts"],
        [activity, "set_received_new_messages"],
        [message_notifications, "received_messages"],
        [stream_list, "update_streams_sidebar"],
    ]);
    assert.ok(added_message);

    // Despite all of our stubbing/mocking, the call to
    // insert_new_messages will have created a very important
    // side effect that we can verify:
    const inserted_message = message_store.get(new_message.id);
    assert.equal(inserted_message.id, new_message.id);
    assert.equal(inserted_message.content, "example content");
});
