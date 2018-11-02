set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);
zrequire('input_pill');

zrequire('Handlebars', 'handlebars');
zrequire('templates');
global.compile_template('input_pill');

set_global('blueslip', global.make_zblueslip());
set_global('document', {});

var noop = function () {};
var example_img_link = 'http://example.com/example.png';

set_global('ui_util', {
    place_caret_at_end: noop,
});

global.patch_builtin('window', {
    getSelection: () => {
        return {
            anchorOffset: 0,
        };
    },
});

var id_seq = 0;
run_test('set_up_ids', () => {
    // just get coverage on a simple one-liner:
    input_pill.random_id();

    input_pill.random_id = function () {
        id_seq += 1;
        return 'some_id' + id_seq;
    };
});


function pill_html(value, data_id, img_src) {
    var has_image = img_src !== undefined;

    var opts = {
        id: data_id,
        display_value: value,
        has_image: has_image,
    };

    if (has_image) {
        opts.img_src = img_src;
    }

    return templates.render('input_pill', opts);
}

run_test('basics', () => {
    var config = {};

    blueslip.set_test_data('error', 'Pill needs container.');
    input_pill.create(config);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    var pill_input = $.create('pill_input');
    var container = $.create('container');
    container.set_find_results('.input', pill_input);

    blueslip.set_test_data('error', 'Pill needs create_item_from_text');
    config.container = container;
    input_pill.create(config);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    blueslip.set_test_data('error', 'Pill needs get_text_from_item');
    config.create_item_from_text = noop;
    input_pill.create(config);
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();

    config.get_text_from_item = noop;
    var widget = input_pill.create(config);

    var item = {
        display_value: 'JavaScript',
        language: 'js',
        img_src: example_img_link,
    };

    var inserted_before;
    var expected_html = pill_html('JavaScript', 'some_id1', example_img_link);

    pill_input.before = function (elem) {
        inserted_before = true;
        assert.equal(elem.html(), expected_html);
    };

    widget.appendValidatedData(item);
    assert(inserted_before);

    assert.deepEqual(widget.items(), [item]);
});

function set_up() {
    set_global('$', global.make_zjquery());
    var items = {
        blue: {
            display_value: 'BLUE',
            description: 'color of the sky',
            img_src: example_img_link,
        },

        red: {
            display_value: 'RED',
            description: 'color of stop signs',
        },

        yellow: {
            display_value: 'YELLOW',
            description: 'color of bananas',
        },
    };

    var pill_input = $.create('pill_input');

    pill_input.before = () => {};

    var create_item_from_text = function (text) {
        return items[text];
    };

    var container = $.create('container');
    container.set_find_results('.input', pill_input);

    var config = {
        container: container,
        create_item_from_text: create_item_from_text,
        get_text_from_item: (item) => item.display_value,
    };

    id_seq = 0;

    return {
        config: config,
        pill_input: pill_input,
        items: items,
        container: container,
    };
}

run_test('copy from pill', () => {
    const info = set_up();
    const config = info.config;
    const container = info.container;

    const widget = input_pill.create(config);
    widget.appendValue('blue,red');

    const copy_handler = container.get_on_handler('copy', '.pill');

    var copied_text;

    const pill_stub = {
        data: (field) => {
            assert.equal(field, 'id');
            return 'some_id2';
        },
    };

    const e = {
        originalEvent: {
            clipboardData: {
                setData: (format, text) => {
                    assert.equal(format, 'text/plain');
                    copied_text = text;
                },
            },
        },
        preventDefault: noop,
    };

    container.set_find_results(':focus', pill_stub);

    copy_handler(e);

    assert.equal(copied_text, 'RED');
});

run_test('paste to input', () => {
    const info = set_up();
    const config = info.config;
    const container = info.container;
    const items = info.items;

    const widget = input_pill.create(config);

    const paste_handler = container.get_on_handler('paste', '.input');

    var paste_text = 'blue,yellow';

    const e = {
        originalEvent: {
            clipboardData: {
                getData: (format) => {
                    assert.equal(format, 'text/plain');
                    return paste_text;
                },
            },
        },
        preventDefault: noop,
    };

    document.execCommand = (cmd, _, text) => {
        assert.equal(cmd, 'insertText');
        container.find('.input').text(text);
    };

    paste_handler(e);

    assert.deepEqual(widget.items(), [
        items.blue,
        items.yellow,
    ]);
});

run_test('arrows on pills', () => {
    const info = set_up();
    const config = info.config;
    const container = info.container;

    const widget = input_pill.create(config);
    widget.appendValue('blue,red');

    const key_handler = container.get_on_handler('keydown', '.pill');

    function test_key(c) {
        key_handler({
            charCode: c,
        });
    }

    const LEFT_ARROW = 37;
    const RIGHT_ARROW = 39;

    var prev_focused = false;
    var next_focused = false;

    const pill_stub = {
        prev: () => {
            return {
                focus: () => {
                    prev_focused = true;
                },
            };
        },
        next: () => {
            return {
                focus: () => {
                    next_focused = true;
                },
            };
        },
    };

    container.set_find_results('.pill:focus', pill_stub);

    // We use the same stub to test both arrows, since we don't
    // actually cause any real state changes here.  We stub out
    // the only interaction, which is to move the focus.
    test_key(LEFT_ARROW);
    assert(prev_focused);

    test_key(RIGHT_ARROW);
    assert(next_focused);
});

run_test('left arrow on input', () => {
    const info = set_up();
    const config = info.config;
    const container = info.container;

    const widget = input_pill.create(config);
    widget.appendValue('blue,red');

    const LEFT_ARROW = 37;
    const key_handler = container.get_on_handler('keydown', '.input');

    var last_pill_focused = false;

    container.set_find_results('.pill', {
        last: () => {
            return {
                focus: () => {
                    last_pill_focused = true;
                },
            };
        },
    });

    key_handler({
        keyCode: LEFT_ARROW,
    });

    assert(last_pill_focused);
});

run_test('comma', () => {
    const info = set_up();
    const config = info.config;
    const items = info.items;
    const pill_input = info.pill_input;
    const container = info.container;

    const widget = input_pill.create(config);
    widget.appendValue('blue,red');

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
    ]);

    const COMMA = 188;
    const key_handler = container.get_on_handler('keydown', '.input');

    pill_input.text = () => ' yel';

    key_handler({
        keyCode: COMMA,
        preventDefault: noop,
    });

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
    ]);

    pill_input.text = () => ' yellow';

    key_handler({
        keyCode: COMMA,
    });

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
        items.yellow,
    ]);
});

run_test('enter key with text', () => {
    const info = set_up();
    const config = info.config;
    const items = info.items;
    const container = info.container;

    const widget = input_pill.create(config);
    widget.appendValue('blue,red');

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
    ]);

    const ENTER = 13;
    const key_handler = container.get_on_handler('keydown', '.input');

    key_handler({
        keyCode: ENTER,
        preventDefault: noop,
        stopPropagation: noop,
        target: {
            innerText: ' yellow ',
        },
    });

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
        items.yellow,
    ]);
});

run_test('insert_remove', () => {
    const info = set_up();

    const config = info.config;
    const pill_input = info.pill_input;
    const items = info.items;
    const container = info.container;

    var inserted_html = [];
    pill_input.before = function (elem) {
        inserted_html.push(elem.html());
    };

    var widget = input_pill.create(config);

    var created;
    var removed;

    widget.onPillCreate(function () {
        created = true;
    });

    widget.onPillRemove(function () {
        removed = true;
    });

    widget.appendValue('blue,chartreuse,red,yellow,mauve');

    assert(created);
    assert(!removed);

    assert.deepEqual(inserted_html, [
        pill_html('BLUE', 'some_id1', example_img_link),
        pill_html('RED', 'some_id2'),
        pill_html('YELLOW', 'some_id3'),
    ]);

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
        items.yellow,
    ]);

    assert.equal(pill_input.text(), 'chartreuse, mauve');

    assert.equal(widget.is_pending(), true);
    widget.clear_text();
    assert.equal(pill_input.text(), '');
    assert.equal(widget.is_pending(), false);

    var BACKSPACE = 8;
    var key_handler = container.get_on_handler('keydown', '.input');

    key_handler({
        keyCode: BACKSPACE,
        target: {
            innerText: '',
        },
        preventDefault: noop,
    });

    assert(removed);

    assert.deepEqual(widget.items(), [
        items.blue,
        items.red,
    ]);

    var next_pill_focused = false;

    const next_pill_stub = {
        focus: () => {
            next_pill_focused = true;
        },
    };

    const focus_pill_stub = {
        next: () => next_pill_stub,
        data: (field) => {
            assert.equal(field, 'id');
            return 'some_id1';
        },
    };

    container.set_find_results('.pill:focus', focus_pill_stub);

    key_handler = container.get_on_handler('keydown', '.pill');
    key_handler({
        keyCode: BACKSPACE,
        preventDefault: noop,
    });

    assert(next_pill_focused);
});

run_test('exit button on pill', () => {
    const info = set_up();

    const config = info.config;
    const items = info.items;
    const container = info.container;

    const widget = input_pill.create(config);

    widget.appendValue('blue,red');

    var next_pill_focused = false;

    const next_pill_stub = {
        focus: () => {
            next_pill_focused = true;
        },
    };

    const curr_pill_stub = {
        next: () => next_pill_stub,
        data: (field) => {
            assert.equal(field, 'id');
            return 'some_id1';
        },
    };

    const exit_button_stub = {
        to_$: () => {
            return {
                closest: (sel) => {
                    assert.equal(sel, '.pill');
                    return curr_pill_stub;
                },
            };
        },
    };

    var e = {
        stopPropagation: noop,
    };
    const exit_click_handler = container.get_on_handler('click', '.exit');

    exit_click_handler.apply(exit_button_stub, [e]);

    assert(next_pill_focused);

    assert.deepEqual(widget.items(), [
        items.red,
    ]);

});

run_test('misc things', () => {
    const info = set_up();

    const config = info.config;
    const container = info.container;
    const pill_input = info.pill_input;

    const widget = input_pill.create(config);

    // animation
    const animation_end_handler = container.get_on_handler('animationend', '.input');

    var shake_class_removed = false;

    const input_stub = {
        to_$: () => {
            return {
                removeClass: (cls) => {
                    assert.equal(cls, 'shake');
                    shake_class_removed = true;
                },
            };
        },
    };

    animation_end_handler.apply(input_stub);
    assert(shake_class_removed);

    // bad data
    blueslip.set_test_data('error', 'no display_value returned');
    widget.appendValidatedData('this-has-no-item-attribute');

    // click on container
    const container_click_handler = container.get_on_handler('click');

    const stub = $.create('the-pill-container');
    stub.set_find_results('.input', pill_input);
    stub.is = (sel) => {
        assert.equal(sel, '.pill-container');
        return true;
    };

    const this_ = {
        to_$: () => stub,
    };

    container_click_handler.call(this_, {target: this_});
});
