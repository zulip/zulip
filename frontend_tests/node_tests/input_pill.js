set_global('$', global.make_zjquery());
zrequire('input_pill');

zrequire('Handlebars', 'handlebars');
zrequire('templates');
global.compile_template('input_pill');

set_global('blueslip', {
});

var noop = function () {};

set_global('ui_util', {
    place_caret_at_end: noop,
});

var id_seq = 0;

(function set_up_ids() {
    // just get coverage on a simple one-liner:
    input_pill.random_id();

    input_pill.random_id = function () {
        id_seq += 1;
        return 'some_id' + id_seq;
    };
}());


function pill_html(value, data_id) {
    var opts = {
        id: data_id,
        display_value: value,
    };

    return templates.render('input_pill', opts);
}

(function test_basics() {
    var error;

    var config = {};

    blueslip.error = function (err) {
        error = err;
    };

    input_pill.create(config);
    assert.equal(error, 'Pill needs container.');

    var pill_input = $.create('pill_input');
    var container = $.create('container');
    container.set_find_results('.input', pill_input);

    config.container = container;
    input_pill.create(config);
    assert.equal(error, 'Pill needs create_item_from_text');

    config.create_item_from_text = noop;
    input_pill.create(config);
    assert.equal(error, 'Pill needs get_text_from_item');

    blueslip.error = function () {
        throw "unexpected error";
    };

    config.get_text_from_item = noop;
    var widget = input_pill.create(config);

    var item = {
        display_value: 'JavaScript',
        language: 'js',
    };

    var inserted_before;
    var expected_html = pill_html('JavaScript', 'some_id1');

    pill_input.before = function (elem) {
        inserted_before = true;
        assert.equal(elem.html(), expected_html);
    };

    widget.appendValidatedData(item);
    assert(inserted_before);

    assert.deepEqual(widget.items(), [item]);
}());

(function test_insert_remove() {
    set_global('$', global.make_zjquery());
    var items = {
        blue: {
            display_value: 'BLUE',
            description: 'color of the sky',
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

    var inserted_html = [];
    pill_input.before = function (elem) {
        inserted_html.push(elem.html());
    };

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


    // FINALLY CREATE THE WIDGET!!
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
        pill_html('BLUE', 'some_id1'),
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
}());
