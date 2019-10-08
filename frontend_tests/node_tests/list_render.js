zrequire('list_render');

// We need these stubs to get by instanceof checks.
// The list_render library allows you to insert objects
// that are either jQuery, Element, or just raw HTML
// strings.  We initially test with raw strings.
set_global('jQuery', 'stub');
set_global('Element', function () {
    return { };
});

// We only need very simple jQuery wrappers for when the
// "real" code wraps html or sets up click handlers.
// We'll simulate most other objects ourselves.
set_global('$', (arg) => {
    if (arg.to_jquery) {
        return arg.to_jquery();
    }

    return {
        html: () => arg,
    };
});

function make_containers() {
    // We build objects here that simulate jQuery containers.
    // The main thing to do at first is simulate that our
    // parent container is the nearest ancestor to our main
    // container that has a max-height attribute, and then
    // the parent container will have a scroll event attached to
    // it.  This is a good time to read __set_events in the
    // real code.
    const parent_container = {};
    const container = {};

    container.parent = () => parent_container;
    container.length = () => 1;
    container.is = () => false;
    container.css = (prop) => {
        assert.equal(prop, 'max-height');
        return 'none';
    };

    parent_container.is = () => false;
    parent_container.length = () => 1;
    parent_container.css = (prop) => {
        assert.equal(prop, 'max-height');
        return 100;
    };

    // Capture the scroll callback so we can call it in
    // our tests.
    parent_container.scroll = (f) => {
        parent_container.call_scroll = () => {
            f.call(parent_container);
        };
    };

    // Make our append function just set a field we can
    // check in our tests.
    container.append = (data) => {
        container.appended_data = data;
    };

    return {
        container: container,
        parent_container: parent_container,
    };
}

function make_search_input() {
    const $element = {};

    // Allow ourselves to be wrapped by $(...) and
    // return ourselves.
    $element.to_jquery = () => $element;

    $element.on = (event_name, f) => {
        assert.equal(event_name, 'input');
        $element.simulate_input_event = () => {
            const elem = {
                value: $element.val(),
            };
            f.call(elem);
        };
    };

    return $element;
}

function div(item) {
    return '<div>' + item + '</div>';
}

run_test('list_render', () => {
    const {container, parent_container} = make_containers();

    const search_input = make_search_input();

    const list = [
        'apple',
        'banana',
        'carrot',
        'dog',
        'egg',
        'fence',
        'grape',
    ];
    const opts = {
        filter: {
            element: search_input,
        },
        load_count: 2,
        modifier: (item) => div(item),
    };

    const widget = list_render.create(container, list, opts);

    widget.render();

    var expected_html = '<div>apple</div><div>banana</div>';
    assert.deepEqual(container.appended_data.html(), expected_html);

    // Set up our fake geometry so it forces a scroll action.
    parent_container.scrollTop = 180;
    parent_container.clientHeight = 100;
    parent_container.scrollHeight = 260;

    // Scrolling gets the next two elements from the list into
    // our widget.
    parent_container.call_scroll();
    expected_html = '<div>carrot</div><div>dog</div>';
    assert.deepEqual(container.appended_data.html(), expected_html);

    // Filtering will pick out dog/egg/grape when we put "g"
    // into our search input.  (This uses the default filter, which
    // is a glorified indexOf call.)
    container.html = (html) => { assert.equal(html, ''); };
    search_input.val = () => 'g';
    search_input.simulate_input_event();
    expected_html = '<div>dog</div><div>egg</div><div>grape</div>';
    assert.deepEqual(container.appended_data.html(), expected_html);

    // We can insert new data into the widget.
    const new_data = [
        'greta',
        'faye',
        'gary',
        'frank',
        'giraffe',
        'fox',
    ];

    widget.data(new_data);
    widget.render();
    expected_html = '<div>greta</div><div>gary</div>';
    assert.deepEqual(container.appended_data.html(), expected_html);
});

function sort_button(opts) {
    // The complications here are due to needing to find
    // the list via complicated HTML assumptions. Also, we
    // don't have any abstraction for the button and its
    // siblings other than direct jQuery actions.

    function data(sel) {
        switch (sel) {
        case "sort": return opts.sort_type;
        case "sort-prop": return opts.prop_name;
        default: throw Error('unknown selector: ' + sel);
        }
    }

    function lookup(sel, value) {
        return (selector) => {
            assert.equal(sel, selector);
            return value;
        };
    }

    var button;

    const $button = {
        data: data,
        parents: lookup('table', {
            next: lookup('.progressive-table-wrapper', {
                data: lookup('list-render', opts.list_name),
            }),
        }),
        hasClass: lookup('active', opts.active),
        siblings: lookup('.active', {
            removeClass: (sel) => {
                assert.equal(sel, 'active');
                button.siblings_deactivated = true;
            },
        }),
        addClass: (sel) => {
            assert.equal(sel, 'active');
            button.activated = true;
        },
    };

    button = {
        to_jquery: () => $button,
        siblings_deactivated: false,
        activated: false,
    };

    return button;
}

run_test('sorting', () => {
    const {container} = make_containers();

    var cleared;
    container.html = (html) => {
        assert.equal(html, '');
        cleared = true;
    };

    const alice = { name: 'alice', salary: 50 };
    const bob = { name: 'bob', salary: 40 };
    const cal = { name: 'cal', salary: 30 };
    const dave = { name: 'dave', salary: 25 };

    const list = [bob, dave, alice, cal];

    const opts = {
        name: 'my-list',
        load_count: 2,
        modifier: (item) => {
            return div(item.name) + div(item.salary);
        },
    };

    function html_for(people) {
        return _.map(people, opts.modifier).join('');
    }

    list_render.create(container, list, opts);

    var button_opts;
    var button;
    var expected_html;

    button_opts = {
        sort_type: 'alphabetic',
        prop_name: 'name',
        list_name: 'my-list',
        active: false,
    };

    button = sort_button(button_opts);

    list_render.handle_sort.call(button);

    assert(cleared);
    assert(button.siblings_deactivated);

    expected_html = html_for([alice, bob, cal, dave]);
    assert.deepEqual(container.appended_data.html(), expected_html);

    // Now try a numeric sort.
    button_opts = {
        sort_type: 'numeric',
        prop_name: 'salary',
        list_name: 'my-list',
        active: false,
    };

    button = sort_button(button_opts);

    cleared = false;
    button.siblings_deactivated = false;

    list_render.handle_sort.call(button);

    assert(cleared);
    assert(button.siblings_deactivated);

    expected_html = html_for([dave, cal, bob, alice]);
    assert.deepEqual(container.appended_data.html(), expected_html);
});
