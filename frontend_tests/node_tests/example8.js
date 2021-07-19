"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

/*
    Until now, we had seen various testing techniques, learnt
    how to use helper functions like `mock_esm`, `override` of
    `run_test` etc., but we didn't see how to deal with
    render calls to handlebars templates. We'll learn that
    in this test.

    The below code tests the rendering of alert words in settings UI
    i.e., render_alert_words_ui function of static/js/alert_words_ui.js.
*/

const alert_words = zrequire("alert_words");
const alert_words_ui = zrequire("alert_words_ui");

// Let's first add a few alert words.
alert_words.initialize({
    alert_words: ["foo", "bar"],
});

/*
    Notice the `mock_template` in the object passed to `run_test` wrapper below.
    It is pretty similar to `override` we've seen in previous examples but
    mocks a template instead of a js function.

    Just like `override`, `mock_template` lets us run a function taking in
    the arguments passed to the template. Additionally, we can also have
    the rendered html passed as an argument.

    It's usage below will make it more clear to you.
*/
run_test("render_alert_words_ui", ({mock_template}) => {
    const word_list = $("#alert_words_list");

    // All the alert word elements will be rendered in `#alert_words_list`. That is
    // done with the help of `append` in actual code. We can test that all alert words
    // are added to it by making its `append` add the values passed to it to an array
    // as shown below and verifying its contents later.
    const appended = [];
    word_list.append = (rendered) => {
        appended.push(rendered);
    };

    // Existing alert words in the actual code are removed before adding them
    // to avoid duplicates by calling `remove` on find results of `#alert_words_list`.
    // We make sure that doesn't fail by creating stubs here.
    const alert_word_items = $.create("alert_word_items");
    word_list.set_find_results(".alert-word-item", alert_word_items);
    alert_word_items.remove = () => {};

    // As you can see below, the first argument to mock_template takes
    // the relative path of the template we want to mock w.r.t static/templates/
    //
    // The second argument takes a boolean determing whether to render html.
    // We mostly set this to `false` and recommend you avoid setting this to `true`
    // unless necessary in situations where you want to test conditionals
    // or something similar. Find and see examples where we set this to true with
    // help of `git grep mock_template | grep true`.
    //
    // The third takes a function to run on calling this template. The function
    // gets passed an object(`args` below) containing arguments passed to the template.
    // Additionally, it can also have rendered html passed to it if second argument of
    // mock_template was set to true. Any render calls to this template
    // will run the function and return the function's return value.
    mock_template("settings/alert_word_settings_item.hbs", false, (args) => "stub-" + args.word);

    // On redering alert words UI, `#create_alert_word_name` will be focused.
    // Create a stub for that and make sure it isn't focused now but is focused
    // after calling `render_alert_words_ui`.
    const new_alert_word = $("#create_alert_word_name");
    assert.ok(!new_alert_word.is_focused());

    // This is the function we are testing. It gets all the alert words which
    // are added with `alert_words.initialize` above, renders each alert word nicely
    // with the help of `alert_word_settings_item.hbs`, appends each of those rendered
    // elements to #alert_words_list and focuses #create_alert_word.
    alert_words_ui.render_alert_words_ui();

    // If you missed it, the `stub-` part prepended to alert words is an effect
    // of the return value of the function passed into `mock_template` call above.
    assert.deepEqual(appended, ["stub-bar", "stub-foo"]);
    assert.ok(new_alert_word.is_focused());
});
