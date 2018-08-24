set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);
zrequire('input_pill');

zrequire('Handlebars', 'handlebars');
zrequire('templates');
global.compile_template('input_pill');

set_global('blueslip', global.make_zblueslip());

var noop = function () {};
var example_img_link = 'http://example.com/example.png';

set_global('ui_util', {
    place_caret_at_end: noop,
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

    var create_item_from_text = function (text) {
        return items[text];
    };

    var container = $.create('container');
    container.set_find_results('.input', pill_input);

    var config = {
        container: container,
        create_item_from_text: create_item_from_text,
        get_text_from_item: noop,
    };

    id_seq = 0;

    return {
        config: config,
        pill_input: pill_input,
        items: items,
        container: container,
    };
}

run_test('comma', () => {
    const info = set_up();
    const config = info.config;
    const items = info.items;
    const pill_input = info.pill_input;
    const container = info.container;

    const widget = input_pill.create(config);

    pill_input.before = () => {};

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
    const pill_input = info.pill_input;
    const container = info.container;

    const widget = input_pill.create(config);

    pill_input.before = () => {};

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

    widget.clear_text();
    assert.equal(pill_input.text(), '');

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
