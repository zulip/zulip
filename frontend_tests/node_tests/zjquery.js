/*

This test module actually tests our test code, particularly zjquery, and
it is intended to demonstrate how to use zjquery (as well as, of course, verify
that it works as advertised).

What is zjquery?

    The zjquery test module behaves like jQuery at a very surface level, and it
    allows you to test code that uses actual jQuery without pulling in all the
    complexity of jQuery.  It also allows you to mostly simulate DOM for the
    purposes of unit testing, so that your tests focus on component interactions
    that aren't super tightly coupled to building the DOM.  The tests also run
    faster!

The code we are testing lives here:

    https://github.com/zulip/zulip/blob/master/frontend_tests/zjsunit/zjquery.js

*/


// The first thing we do to use zjquery is patch our global namespace
// with zjquery as follows.  This call gives us our own instance of a
// zjquery stub variable.  Like with real jQuery, the '$' function will
// be the gateway to a bigger API.
set_global('$', global.make_zjquery());


(function test_basics() {
    // Let's create a sample piece of code to test:

    function show_my_form() {
        $('#my-form').show();
    }

    // Before we call show_my_form, we can assert that my-form is hidden:
    assert(!$('#my-form').visible());

    // Then calling show_my_form() should make it visible.
    show_my_form();
    assert($('#my-form').visible());

    // Next, look at how several functions correctly simulate setting
    // and getting for you.
    var widget = $('#my-widget');

    widget.attr('data-employee-id', 42);
    assert.equal(widget.attr('data-employee-id'), 42);

    widget.html('<b>hello</b>');
    assert.equal(widget.html(), '<b>hello</b>');

    widget.text('goodbye');
    assert.equal(widget.text(), 'goodbye');

    widget.prop('title', 'My Widget');
    assert.equal(widget.prop('title'), 'My Widget');

    widget.val('42');
    assert.equal(widget.val(), '42');

}());

(function test_parent_child_stuff() {
    // Let's say you have a function like the following:
    function update_message_emoji(emoji_src) {
        $('#my-message').find('.emoji').attr('src', emoji_src);
    }

    // This would explode:
    // update_message_emoji('foo.png');

    // The error would be:
    // Error: Cannot find .emoji in #my-message

    // But you can set up your tests to simulate DOM relationships.
    //
    // We will use add_child(), which is a special zjquery helper.
    var emoji = $('emoji-stub');
    $('#my-message').add_child('.emoji', emoji);

    // And then calling the function produces the desired effect:
    update_message_emoji('foo.png');
    assert.equal(emoji.attr('src'), 'foo.png');

}());

(function test_clicks() {
    // We can support basic handlers like click and keydown.

    var state = {};

    function set_up_click_handlers () {
        $('#widget1').click(function () {
            state.clicked = true;
        });

        $('.some-class').keydown(function () {
            state.keydown = true;
        });
    }

    // Setting up the click handlers doesn't change state right away.
    set_up_click_handlers();
    assert(!state.clicked);
    assert(!state.keydown);

    // But we can simulate clicks.
    $('#widget1').click();
    assert.equal(state.clicked, true);

    // and keydown
    $('.some-class').keydown();
    assert.equal(state.keydown, true);

}());

(function test_events() {
    // Zulip's codebase uses jQuery's event API heavily with anonymous
    // functions that are hard for naive test code to cover.  zjquery
    // will come to our rescue.

    var value;

    function initialize_handler() {
        $('my-parent').on('input', '.some-child-class', function (e) {
            value = 42; // just a dummy side effect
            e.stopPropagation();
        });
    }

    // Calling initialize_handler() doesn't immediately do much of interest.
    initialize_handler();
    assert.equal(value, undefined);

    // We want to call the inner function, so first let's get it using the
    // get_on_handler() helper from zjquery.
    var handler_func = $('my-parent').get_on_handler('input', '.some-child-class');

    // Set up a stub event so that stopPropagation doesn't explode on us.
    var stub_event = {
        stopPropagation: function () {},
    };

    // Now call the hander.
    handler_func(stub_event);

    // And verify it did what it was supposed to do.
    assert.equal(value, 42);
}());
