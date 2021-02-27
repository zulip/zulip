"use strict";

// This is a general tour of how to write node tests that
// may also give you some quick insight on how the Zulip
// browser app is constructed.

// The statements below are pretty typical for most node
// tests. The reason we need these helpers will hopefully
// become clear as you keep reading.
const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");

// Some quick housekeeping:  Let's clear page_params, which is a data
// structure that the server sends down to us when the app starts.  We
// prefer to test with a clean slate.

set_global("page_params", {});

const activity = set_global("activity", {});
const message_live_update = set_global("message_live_update", {});
const pm_list = set_global("pm_list", {});
const settings_users = set_global("settings_users", {});
const home_msg_list = set_global("home_msg_list", {});
const message_list = set_global("message_list", {});
const message_util = set_global("message_util", {});
const notifications = set_global("notifications", {});
const overlays = set_global("overlays", {});
const resize = set_global("resize", {});
let stream_list = set_global("stream_list", {});
let unread_ops = set_global("unread_ops", {});
const unread_ui = set_global("unread_ui", {});
const channel = {__esModule: true};
rewiremock("../../static/js/channel").with(channel);
const message_viewport = set_global("message_viewport", {});
const topic_list = set_global("topic_list", {});

rewiremock.enable();

// Let's start with testing a function from util.js.
//
// We will use our special zrequire helper to import the
// code from util. We use zrequire instead of require,
// because it has some magic to clear state when we move
// on to the next test.
//
// The most basic unit tests load up code, call functions,
// and assert truths:

const util = zrequire("util");
assert(!util.find_wildcard_mentions("boring text"));
assert(util.find_wildcard_mentions("mention @**everyone**"));

// Let's test with people.js next.  We'll show this technique:
//  * get a false value
//  * change the data
//  * get a true value

const people = zrequire("people");
const isaac = {
    email: "isaac@example.com",
    user_id: 30,
    full_name: "Isaac Newton",
};

assert(!people.is_known_user_id(isaac.user_id));
people.add_active_user(isaac);
assert(people.is_known_user_id(isaac.user_id));

// The `people`object is a very fundamental object in the
// Zulip app.  You can learn a lot more about it by reading
// the tests in people.js in the same directory as this file.
// Let's create the current user, which some future tests will
// require.

const me = {
    email: "me@example.com",
    user_id: 31,
    full_name: "Me Myself",
};
people.add_active_user(me);
people.initialize_current_user(me.user_id);

// Let's look at stream_data next, and we will start by putting
// some data at module scope (since it may be useful for future
// tests):

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

// We use both set_global and zrequire here for test isolation.
//
// We also introduce the run_test helper, which mostly just causes
// a line of output to go to the console. It does a little more than
// that, which we will see later.

const stream_data = zrequire("stream_data");

run_test("verify stream_data persists stream color", () => {
    assert.equal(stream_data.get_sub_by_name("Denmark"), undefined);
    stream_data.add_sub(denmark_stream);
    const sub = stream_data.get_sub_by_name("Denmark");
    assert.equal(sub.color, "blue");
});

// Hopefully the basic patterns for testing data-oriented modules
// are starting to become apparent.  To reinforce that, we will present
// few more examples that also expose you to some of our core
// data objects.  Also, we start testing some objects that have
// deeper dependencies.

const messages = {
    isaac_to_denmark_stream: {
        id: 400,
        sender_id: isaac.user_id,
        stream_id: denmark_stream.stream_id,
        type: "stream",
        flags: ["has_alert_word"],
        topic: "copenhagen",
        // note we don't have every field that a "real" message
        // would have, and that can be fine
    },
};

// We are going to test a core module called messages_store.js next.
// This is an example of a deep unit test, where our dependencies
// are easy to test.  Start by requiring the dependencies:
zrequire("recent_senders");
const unread = zrequire("unread");
const stream_topic_history = zrequire("stream_topic_history");
const recent_topics = zrequire("recent_topics");

// And finally require the module that we will test directly:
const message_store = zrequire("message_store");

run_test("message_store", () => {
    const in_message = {...messages.isaac_to_denmark_stream};

    assert.equal(in_message.alerted, undefined);
    message_store.set_message_booleans(in_message);
    assert.equal(in_message.alerted, true);

    // Let's add a message into our message_store via
    // add_message_metadata.
    assert.equal(message_store.get(in_message.id), undefined);
    message_store.add_message_metadata(in_message);
    const message = message_store.get(in_message.id);
    assert.equal(message, in_message);

    // There are more side effects.
    const topic_names = stream_topic_history.get_recent_topic_names(denmark_stream.stream_id);
    assert.deepEqual(topic_names, ["copenhagen"]);
});

// Tracking unread messages is a very fundamental part of the Zulip
// app, and we use the unread object to track unread messages.

run_test("unread", () => {
    const stream_id = denmark_stream.stream_id;
    const topic_name = "copenhagen";

    assert.equal(unread.num_unread_for_topic(stream_id, topic_name), 0);

    const in_message = {...messages.isaac_to_denmark_stream};
    message_store.set_message_booleans(in_message);

    unread.process_loaded_messages([in_message]);
    assert.equal(unread.num_unread_for_topic(stream_id, topic_name), 1);
});

// In the Zulip app you can narrow your message stream by topic, by
// sender, by PM recipient, by search keywords, etc.  We will discuss
// narrows more broadly, but first let's test out a core piece of
// code that makes things work.

// We use the second argument of zrequire to find the location of the
// Filter class.
const Filter = zrequire("Filter", "js/filter");

run_test("filter", () => {
    const filter_terms = [
        {operator: "stream", operand: "Denmark"},
        {operator: "topic", operand: "copenhagen"},
    ];

    const filter = new Filter(filter_terms);

    const predicate = filter.predicate();

    // We don't need full-fledged messages to test the gist of
    // our filter.  If there are details that are distracting from
    // your test, you should not feel guilty about removing them.
    assert.equal(predicate({type: "personal"}), false);

    assert.equal(
        predicate({
            type: "stream",
            stream_id: denmark_stream.stream_id,
            topic: "does not match filter",
        }),
        false,
    );

    assert.equal(
        predicate({
            type: "stream",
            stream_id: denmark_stream.stream_id,
            topic: "copenhagen",
        }),
        true,
    );
});

// We have a "narrow" abstraction that sits roughly on top of the
// "filter" abstraction.  If you are in a narrow, we track the
// state with the narrow_state module.

const narrow_state = zrequire("narrow_state");

run_test("narrow_state", () => {
    // As we often do, first make assertions about the starting
    // state:

    assert.equal(narrow_state.stream(), undefined);

    // Now set the state.
    const filter_terms = [
        {operator: "stream", operand: "Denmark"},
        {operator: "topic", operand: "copenhagen"},
    ];

    const filter = new Filter(filter_terms);

    narrow_state.set_current_filter(filter);

    assert.equal(narrow_state.stream(), "Denmark");
    assert.equal(narrow_state.topic(), "copenhagen");
});

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
    at people.js in this directory for more tests on the
    people object.

    We can quickly review some testing concepts:

        zrequire - bring in real code
        set_global - create stubs
        assert.equal - verify results

    ------

    It's time to elaborate a bit on set_global.

    First, some context.  When we test certain objects,
    we don't always want to test all the code they
    depend on.  Often we want to completely ignore the
    interactions with certain objects; other times, we
    will want to simulate some behavior of the objects
    we depend on without bringing in all the implementation
    details.

    Also, our test runner runs many tests back to back.
    Between each test we need to essentially reset the global
    object back to its original state, so that state doesn't
    leak between tests.

    That's where set_global comes in.  When you call
    set_global, it updates the global namespace with an
    object that you specify in the **test**, not real
    code.  Using set_global explicitly tells your test
    reader what your testing boundaries are between "real"
    code and "simulated" code.  Finally, and perhaps most
    importantly, the test runner will prevent this state
    from leaking into the next test (and "zrequire" has
    the same behavior attached to it as well).

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

const server_events_dispatch = zrequire("server_events_dispatch");

// We will use Bob in several tests.
const bob = {
    email: "bob@example.com",
    user_id: 33,
    full_name: "Bob Roberts",
};

run_test("add_user_event", () => {
    const event = {
        type: "realm_user",
        op: "add",
        person: bob,
    };

    assert(!people.is_known_user_id(bob.user_id));
    server_events_dispatch.dispatch_normal_event(event);
    assert(people.is_known_user_id(bob.user_id));
});

/*

   It's actually a little surprising that adding a user does
   not have side effects beyond the people object.  I guess
   we don't immediately update the buddy list, but that's
   because the buddy list gets updated on the next server
   fetch.

   Let's try an update next.  To make this work, we will want
   to put some stub objects into the global namespace (as
   opposed to using the "real" code).

   This is where we see a little extra benefit from the
   run_test wrapper.  It passes us in an object that we
   can use to override data, and that works within the
   scope of the function.

*/

const noop = () => {};

zrequire("user_events");

run_test("update_user_event", (override) => {
    const new_bob = {
        email: "bob@example.com",
        user_id: bob.user_id,
        full_name: "The Artist Formerly Known as Bob",
    };

    const event = {
        type: "realm_user",
        op: "update",
        person: new_bob,
    };

    // We have to stub a few things:
    override(activity, "redraw", noop);
    override(message_live_update, "update_user_full_name", noop);
    override(pm_list, "update_private_messages", noop);
    override(settings_users, "update_user_data", noop);

    // Dispatch the realm_user/update event, which will update
    // data structures and have other side effects that are
    // stubbed out above.
    server_events_dispatch.dispatch_normal_event(event);

    const user = people.get_by_user_id(bob.user_id);

    // Verify that the code actually did its main job:
    assert.equal(user.full_name, "The Artist Formerly Known as Bob");
});

/*

   Our test verifies that the update events leads to a name change
   inside the people object, but it obviously kind of glosses over
   the other interactions.

   We can go a step further and verify the sequence of operations
   that happen during an event.  This concept is called "mocking",
   and you can find libraries to help do mocking.  Here we will
   just build our own lightweight mocking system, which is almost
   trivially easy to do in a language like JavaScript.

*/

function test_helper() {
    const events = [];

    return {
        redirect: (module, func_name) => {
            module[func_name] = () => {
                events.push([module, func_name]);
            };
        },
        events,
    };
}

/*

   Our test_helper will allow us to redirect methods to an
   events array, and we can then later verify that the sequence
   of side effect is as predicted.

   (Note that for now we don't simulate return values nor do we
   inspect the arguments to these functions.  We could easily
   extend our helper to do more.)

   The forthcoming example is a pretty extreme example, where we
   are calling a pretty high level method that dispatches
   a lot of its work out to other objects.

*/

const huddle_data = zrequire("huddle_data");
const message_events = zrequire("message_events");

run_test("insert_message", (override) => {
    override(pm_list, "update_private_messages", noop);

    const helper = test_helper();
    set_global((recent_topics.is_visible = () => false));

    const new_message = {
        sender_id: isaac.user_id,
        id: 1001,
        content: "example content",
    };

    assert.equal(message_store.get(new_message.id), undefined);

    helper.redirect(huddle_data, "process_loaded_messages");
    helper.redirect(message_util, "add_new_messages");
    helper.redirect(notifications, "received_messages");
    helper.redirect(resize, "resize_page_components");
    helper.redirect(stream_list, "update_streams_sidebar");
    helper.redirect(unread_ops, "process_visible");
    helper.redirect(unread_ui, "update_unread_counts");

    narrow_state.reset_current_filter();

    message_events.insert_new_messages([new_message]);

    // Even though we have stubbed a *lot* of code, our
    // tests can still verify the main "narrative" of how
    // the code invokes various objects when a new message
    // comes in:
    assert.deepEqual(helper.events, [
        [huddle_data, "process_loaded_messages"],
        [message_util, "add_new_messages"],
        [message_util, "add_new_messages"],
        [unread_ui, "update_unread_counts"],
        [resize, "resize_page_components"],
        [unread_ops, "process_visible"],
        [notifications, "received_messages"],
        [stream_list, "update_streams_sidebar"],
    ]);

    // Despite all of our stubbing/mocking, the call to
    // insert_new_messages will have created a very important
    // side effect that we can verify:
    const inserted_message = message_store.get(new_message.id);
    assert.equal(inserted_message.id, new_message.id);
    assert.equal(inserted_message.content, "example content");
});

/*
    The above example is a bit extreme.  Generally we just
    use the make_stub helper that comes with zjsunit.

    We will step away from the actual Zulip codebase for a
    second and just explore a contrived example.
*/

run_test("explore make_stub", (override) => {
    // Let's say you have to test the following code.

    const app = {
        notify_server_of_deposit(deposit_amount) {
            // simulate difficulty
            throw new Error(`We cannot report this value without wifi: ${deposit_amount}`);
        },

        pop_up_fancy_confirmation_screen(deposit_amount, label) {
            // simulate difficulty
            throw new Error(`We cannot make a ${label} dialog for amount ${deposit_amount}`);
        },
    };

    let balance = 40;

    function deposit_paycheck(paycheck_amount) {
        balance += paycheck_amount;
        app.notify_server_of_deposit(paycheck_amount);
        app.pop_up_fancy_confirmation_screen(paycheck_amount, "paycheck");
    }

    // Our deposit_paycheck should be easy to unit test for its
    // core functionality (updating your balance), but the side
    // effects get in the way.  We have to override them to do
    // the simple test here.

    with_field(app, "notify_server_of_deposit", noop, () => {
        with_field(app, "pop_up_fancy_confirmation_screen", noop, () => {
            deposit_paycheck(10);
        });
    });
    assert.equal(balance, 50);

    // But we can do a little better here.  Even though
    // the two side-effect functions are awkward here, we can
    // at least make sure they are invoked correctly.  Let's
    // use stubs.

    const notify_stub = make_stub();
    const pop_up_stub = make_stub();

    // This time we'll just use our override helper to connect the
    // stubs.
    override(app, "notify_server_of_deposit", notify_stub.f);
    override(app, "pop_up_fancy_confirmation_screen", pop_up_stub.f);

    deposit_paycheck(25);
    assert.equal(balance, 75);

    assert.deepEqual(notify_stub.get_args("amount"), {amount: 25});
    assert.deepEqual(pop_up_stub.get_args("amount", "label"), {amount: 25, label: "paycheck"});
});

/*

   Let's continue to explore how we can test complex
   interactions in the real code.

   When a new message comes in, we update the three major
   panes of the app:

        * left sidebar - stream list
        * middle pane - message view
        * right sidebar - buddy list (aka "activity" list)

    These are reflected by the following calls:

        stream_list.update_streams_sidebar
        message_util.add_new_messages
        activity.process_loaded_messages

    For now, though, let's focus on another side effect
    of processing incoming messages:

        unread_ops.process_visible

    When new messages come in, they are often immediately
    visible to users, so the app will communicate this
    back to the server by calling unread_ops.process_visible.

    In order to unit test this, we don't want to require
    an actual server to be running.  Instead, this example
    will stub many of the "boundaries" to focus on the
    core behavior.

*/

zrequire("message_flags");

unread_ops = zrequire("unread_ops");

run_test("unread_ops", (override) => {
    (function set_up() {
        const test_messages = [
            {
                id: 50,
                type: "stream",
                stream_id: denmark_stream.stream_id,
                topic: "copenhagen",
                unread: true,
            },
        ];

        // Make our test message appear to be unread, so that
        // we then need to subsequently process them as read.
        unread.process_loaded_messages(test_messages);

        // Make our window appear visible.
        override(notifications, "is_window_focused", () => true);

        // Make our "test" message appear visible.
        override(message_viewport, "bottom_message_visible", () => true);

        // Make us not be in a narrow (somewhat hackily).
        message_list.narrowed = undefined;

        // Set current_message_list containing messages that
        // can be marked read
        set_global("current_msg_list", {
            all_messages: () => test_messages,
            can_mark_messages_read: () => true,
        });

        // Ignore these interactions for now:
        message_list.all = {
            show_message_as_read() {},
        };
        override(home_msg_list, "show_message_as_read", noop);
        override(notifications, "close_notification", noop);
    })();

    // Set up a way to capture the options passed in to channel.post.
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    // Let the real code skip over details related to active overlays.
    override(overlays, "is_active", () => false);

    // First, test for a message list that cannot read messages.  Here
    // we use with_field to limit the scope of our stub function.
    with_field(
        current_msg_list,
        "can_mark_messages_read",
        () => false,
        () => {
            unread_ops.process_visible();
        },
    );

    assert.deepEqual(channel_post_opts, undefined);

    with_field(
        current_msg_list,
        "can_mark_messages_read",
        () => true,
        () => {
            // Do the main thing we're testing!
            unread_ops.process_visible();
        },
    );

    // The most important side effect of the above call is that
    // we post info to the server.  We can verify that the correct
    // url and parameters are specified:
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        idempotent: true,
        data: {messages: "[50]", op: "add", flag: "read"},
        success: channel_post_opts.success,
    });
});

/*

   Next we will explore this function:

      stream_list.update_streams_sidebar

    To make this test work, we will create a somewhat elaborate
    function that fills in for jQuery (https://jquery.com/), so that
    one boundary of our tests is how stream_list.js calls into
    stream_list to manipulate DOM.

*/

stream_list = zrequire("stream_list");

const social_stream = {
    color: "red",
    name: "Social",
    stream_id: 102,
    subscribed: true,
};

function jquery_elem() {
    // We create basic stubs for jQuery elements, so they
    // just work.  We can extend these in cases where we want
    // more detailed testing.
    const elem = {};

    elem.expectOne = () => elem;
    elem.removeClass = () => elem;
    elem.empty = () => elem;

    return elem;
}

function make_jquery_helper() {
    const stream_list_filter = jquery_elem();
    stream_list_filter.val = () => "";

    const stream_filters = jquery_elem();

    let appended_data;
    stream_filters.append = (data) => {
        appended_data = data;
    };

    function fake_jquery(selector) {
        switch (selector) {
            case ".stream-list-filter":
                return stream_list_filter;
            case "ul#stream_filters li":
                return jquery_elem();
            case "#stream_filters":
                return stream_filters;
            default:
                throw new Error("unknown selector: " + selector);
        }
    }

    set_global("$", fake_jquery);

    return {
        verify_actions: () => {
            const expected_data_to_append = [["stream stub"]];

            assert.deepEqual(appended_data, expected_data_to_append);
        },
    };
}

function make_topic_list_helper(override) {
    // We want to make sure that updating a stream_list
    // closes the topic list and then rebuilds it.  We don't
    // care about the implementation details of topic_list for
    // now, just that it is invoked properly.
    override(topic_list, "active_stream_id", () => undefined);
    override(topic_list, "get_stream_li", () => undefined);

    let topic_list_cleared;
    override(topic_list, "clear", () => {
        topic_list_cleared = true;
    });

    let topic_list_closed;
    override(topic_list, "close", () => {
        topic_list_closed = true;
    });

    let topic_list_rebuilt;
    override(topic_list, "rebuild", () => {
        topic_list_rebuilt = true;
    });

    return {
        verify_actions: () => {
            assert(topic_list_cleared);
            assert(topic_list_closed);
            assert(topic_list_rebuilt);
        },
    };
}

function make_sidebar_helper() {
    let updated_whether_active;

    function row_widget() {
        return {
            update_whether_active: () => {
                updated_whether_active = true;
            },
            get_li: () => ["stream stub"],
        };
    }

    stream_list.stream_sidebar.set_row(social_stream.stream_id, row_widget());

    return {
        verify_actions: () => {
            assert(updated_whether_active);
        },
    };
}

run_test("stream_list", (override) => {
    stream_data.add_sub(social_stream);

    const filter_terms = [
        {operator: "stream", operand: "Social"},
        {operator: "topic", operand: "lunch"},
    ];

    const filter = new Filter(filter_terms);

    override(narrow_state, "filter", () => filter);
    override(narrow_state, "active", () => true);

    const jquery_helper = make_jquery_helper();
    const sidebar_helper = make_sidebar_helper();
    const topic_list_helper = make_topic_list_helper(override);

    // This is what we are testing!
    with_field(stream_list, "stream_cursor", {redraw: noop}, () => {
        stream_list.update_streams_sidebar();
    });

    jquery_helper.verify_actions();
    sidebar_helper.verify_actions();
    topic_list_helper.verify_actions();
});
rewiremock.disable();
