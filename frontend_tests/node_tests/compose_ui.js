zrequire('compose_ui');

function make_textbox(s) {
    // Simulate a jQuery textbox for testing purposes.
    var widget = {};

    widget.s = s;
    widget.focused = false;

    widget.caret = function (arg) {
        if (typeof arg === 'number') {
            widget.pos = arg;
            return;
        }

        if (arg) {
            widget.insert_pos = widget.pos;
            widget.insert_text = arg;
            var before = widget.s.slice(0, widget.pos);
            var after = widget.s.slice(widget.pos);
            widget.s = before + arg + after;
            widget.pos += arg.length;
            return;
        }

        return widget.pos;
    };

    widget.focus = function () {
        widget.focused = true;
    };

    widget.blur = function () {
        widget.focused = false;
    };

    widget.val = function () {
        return widget.s;
    };

    return widget;
}

(function test_smart_insert() {
    var textbox = make_textbox('abc ');
    textbox.caret(4);

    compose_ui.smart_insert(textbox, ':smile:');
    assert.equal(textbox.insert_pos, 4);
    assert.equal(textbox.insert_text, ':smile:');
    assert.equal(textbox.val(), 'abc :smile:');
    assert(textbox.focused);

    textbox.blur();
    compose_ui.smart_insert(textbox, ':airplane:');
    assert.equal(textbox.insert_text, ' :airplane:');
    assert.equal(textbox.val(), 'abc :smile: :airplane:');
    assert(textbox.focused);

    // Test the current slightly-broken behavior.
    textbox.caret(0);
    textbox.blur();
    compose_ui.smart_insert(textbox, ':octopus:');
    assert.equal(textbox.insert_text, ':octopus:');
    assert.equal(textbox.val(), ':octopus:abc :smile: :airplane:');
    assert(textbox.focused);

}());

