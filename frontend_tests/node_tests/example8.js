"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

/*
    Until now, we had seen various testing techniques, learned
    how to use helper functions like `mock_esm`, `override` of
    `run_test` etc., but we didn't see how to deal with
    render calls to handlebars templates. We'll learn that
    in this test.

    The below code tests the rendering of typing notifications which
    is handled by the function `typing_events.render_notifications_for_narrow`.
    The function relies on the `typing_notifications.hbs` template for
    rendering html.
    It is worthwhile to read those (they're short and simple) before proceeding
    as that would help better understand the below test.
*/

const typing_events = zrequire("typing_events");
const people = zrequire("people");

// Let us add a few users to use as typists.
const anna = {
    email: "anna@example.com",
    full_name: "Anna Karenina",
    user_id: 8,
};

const vronsky = {
    email: "vronsky@example.com",
    full_name: "Alexei Vronsky",
    user_id: 9,
};

const levin = {
    email: "levin@example.com",
    full_name: "Konstantin Levin",
    user_id: 10,
};

const kitty = {
    email: "kitty@example.com",
    full_name: "Kitty S",
    user_id: 11,
};

people.add_active_user(anna);
people.add_active_user(vronsky);
people.add_active_user(levin);
people.add_active_user(kitty);

/*
    Notice the `mock_template` in the object passed to `run_test` wrapper below.
    It is pretty similar to `override` we've seen in previous examples but
    mocks a template instead of a js function.

    Just like `override`, `mock_template` lets us run a function taking in
    the arguments passed to the template. Additionally, we can also have
    the rendered html passed as an argument.

    It's usage below will make it more clear to you.
*/
run_test("typing_events.render_notifications_for_narrow", ({override_rewire, mock_template}) => {
    // All typists are rendered in `#typing_notifications`.
    const $typing_notifications = $("#typing_notifications");

    const two_typing_users_ids = [anna.user_id, vronsky.user_id];
    const two_typing_users = [anna, vronsky];

    // Based on typing_events.MAX_USERS_TO_DISPLAY_NAME (which is currently 3),
    // we display either the list of all users typing (if they do not exceed
    // MAX_USERS_TO_DISPLAY_NAME) or 'Several people are typing…'

    // As we are not testing any functionality of `get_users_typing_for_narrow`,
    // let's override it to return two typists.
    override_rewire(typing_events, "get_users_typing_for_narrow", () => two_typing_users_ids);

    const two_typing_users_rendered_html = "Two typing users rendered html stub";

    // As you can see below, the first argument of mock_template takes
    // the relative path of the template we want to mock w.r.t static/templates/
    //
    // The second argument takes a boolean determining whether to render html.
    // We mostly set this to `false` and recommend you avoid setting this to `true`
    // unless necessary in situations where you want to test conditionals
    // or something similar. The latter examples below would make that more clear.
    //
    // The third takes a function to run on calling this template. The function
    // gets passed an object(`args` below) containing arguments passed to the template.
    // Additionally, it can also have rendered html passed to it if second argument of
    // mock_template was set to `true`. Any render calls to this template
    // will run the function and return the function's return value.
    //
    // We often use the function in third argument, like below, to make sure
    // the arguments passed to the template are what we expect.
    mock_template("typing_notifications.hbs", false, (args) => {
        assert.deepEqual(args.users, two_typing_users);
        assert.ok(!args.several_users); // Whether to show 'Several people are typing…'
        return two_typing_users_rendered_html;
    });

    typing_events.render_notifications_for_narrow();
    // Make sure #typing_notifications's html content is set to the rendered template
    // which we mocked and gave a custom return value.
    assert.equal($typing_notifications.html(), two_typing_users_rendered_html);

    // Now we'll see how setting the second argument to `true`
    // can be helpful in testing conditionals inside the template.

    // Let's set the mock to just return the rendered html.
    mock_template("typing_notifications.hbs", true, (args, rendered_html) => rendered_html);

    // Since we only have two(<MAX_USERS_TO_DISPLAY_NAME) typists, both of them
    // should be rendered but not 'Several people are typing…'
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes("Several people are typing…"));

    // Change to having four typists and verify the rendered html has
    // 'Several people are typing…' but not the list of users.
    const four_typing_users_ids = [anna.user_id, vronsky.user_id, levin.user_id, kitty.user_id];
    override_rewire(typing_events, "get_users_typing_for_narrow", () => four_typing_users_ids);

    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.html().includes("Several people are typing…"));
    assert.ok(!$typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${levin.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${kitty.full_name} is typing…`));
});
