"use strict";

const {strict: assert} = require("assert");

const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

/*

This test module actually tests our test code, particularly zjquery, and
it is intended to demonstrate how to use zjquery (as well as, of course, verify
that it works as advertised). This test module is a good place to learn how to
stub out functions from jQuery.

What is zjquery?

    The zjquery test module behaves like jQuery at a very surface level, and it
    allows you to test code that uses actual jQuery without pulling in all the
    complexity of jQuery.  It also allows you to mostly simulate DOM for the
    purposes of unit testing, so that your tests focus on component interactions
    that aren't super tightly coupled to building the DOM.  The tests also run
    faster! In order to keep zjquery light, it only has stubs for the most commonly
    used functions of jQuery. This means that it is possible that you may need to
    stub out additional functions manually in the relevant test module.

The code we are testing lives here:

    https://github.com/zulip/zulip/blob/main/web/tests/lib/zjquery.js

*/

run_test("basics", () => {
    // Let's create a sample piece of code to test:

    function show_my_form() {
        $("#my-form").show();
    }

    // Before we call show_my_form, we can assert that my-form is hidden:
    assert.ok(!$("#my-form").visible());

    // Then calling show_my_form() should make it visible.
    show_my_form();
    assert.ok($("#my-form").visible());

    // Next, look at how several functions correctly simulate setting
    // and getting for you.
    const $widget = $("#my-widget");

    $widget.attr("data-employee-id", 42);
    assert.equal($widget.attr("data-employee-id"), 42);
    assert.equal($widget.data("employee-id"), 42);

    $widget.data("department-id", 77);
    assert.equal($widget.attr("data-department-id"), 77);
    assert.equal($widget.data("department-id"), 77);

    $widget.data("department-name", "hr");
    assert.equal($widget.attr("data-department-name"), "hr");
    assert.equal($widget.data("department-name"), "hr");

    $widget.html("<b>hello</b>"); // eslint-disable-line no-jquery/no-parse-html-literal
    assert.equal($widget.html(), "<b>hello</b>");

    $widget.prop("title", "My widget");
    assert.equal($widget.prop("title"), "My widget");

    $widget.val("42");
    assert.equal($widget.val(), "42");
});

run_test("finding_related_objects", () => {
    // Let's say you have a function like the following:
    function update_message_emoji(emoji_src) {
        $("#my-message").find(".emoji").attr("src", emoji_src);
    }

    // This would explode:
    // update_message_emoji('foo.png');

    // The error would be:
    // Error: Cannot find .emoji in #my-message

    // But you can set up your tests to simulate DOM relationships.
    //
    // We will use set_find_results(), which is a special zjquery helper.
    const $emoji = $("<emoji-stub>");
    $("#my-message").set_find_results(".emoji", $emoji);

    // And then calling the function produces the desired effect:
    update_message_emoji("foo.png");
    assert.equal($emoji.attr("src"), "foo.png");

    // Sometimes you want to deliberately test paths that do not find an
    // element. You can pass 'false' as the result for those cases.
    $emoji.set_find_results(".random", false);
    assert.equal($emoji.find(".random").length, 0);
    /*
    An important thing to understand is that zjquery doesn't truly
    simulate DOM.  The way you make relationships work in zjquery
    is that you explicitly set up what your functions want to return.

    Here is another example.
    */

    const $my_parents = $("#folder1,#folder4");
    const $elem = $("#folder555");

    $elem.set_parents_result(".folder", $my_parents);
    $elem.parents(".folder").addClass("active");
    assert.ok($my_parents.hasClass("active"));
});

run_test("clicks", () => {
    // We can support basic handlers like click and keydown.

    const state = {};

    function set_up_click_handlers() {
        $("#widget1").on("click", () => {
            state.clicked = true;
        });

        $(".some-class").on("keydown", () => {
            state.keydown = true;
        });
    }

    // Setting up the click handlers doesn't change state right away.
    set_up_click_handlers();
    assert.ok(!state.clicked);
    assert.ok(!state.keydown);

    // But we can simulate clicks.
    $("#widget1").trigger("click");
    assert.equal(state.clicked, true);

    // and keydown
    $(".some-class").trigger("keydown");
    assert.equal(state.keydown, true);
});

run_test("events", () => {
    // Zulip's codebase uses jQuery's event API heavily with anonymous
    // functions that are hard for naive test code to cover.  zjquery
    // will come to our rescue.

    let value;

    function initialize_handler() {
        $("#my-parent").on("click", ".button-red", (e) => {
            value = "red"; // just a dummy side effect
            e.stopPropagation();
        });

        $("#my-parent").on("click", ".button-blue", (e) => {
            value = "blue";
            e.stopPropagation();
        });
    }

    // Calling initialize_handler() doesn't immediately do much of interest.
    initialize_handler();
    assert.equal(value, undefined);

    // We want to call the inner function, so first let's get it using the
    // get_on_handler() helper from zjquery.
    const red_handler_func = $("#my-parent").get_on_handler("click", ".button-red");

    // Set up a stub event so that stopPropagation doesn't explode on us.
    const stub_event = {
        stopPropagation() {},
    };

    // Now call the handler.
    red_handler_func(stub_event);

    // And verify it did what it was supposed to do.
    assert.equal(value, "red");

    // Test we can have multiple click handlers in the parent.
    const blue_handler_func = $("#my-parent").get_on_handler("click", ".button-blue");
    blue_handler_func(stub_event);
    assert.equal(value, "blue");
});

run_test("create", () => {
    // You can create jQuery objects that aren't tied to any particular
    // selector, and which just have a name.

    const $obj1 = $.create("the table holding employees");
    const $obj2 = $.create("the collection of rows in the table");

    $obj1.show();
    assert.ok($obj1.visible());

    $obj2.addClass(".striped");
    assert.ok($obj2.hasClass(".striped"));
});
