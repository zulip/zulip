"use strict";

const {strict: assert} = require("assert");

const {mock_esm, mock_jquery, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

// We need these stubs to get by instanceof checks.
// The ListWidget library allows you to insert objects
// that are either jQuery, Element, or just raw HTML
// strings.  We initially test with raw strings.
const scroll_util = mock_esm("../src/scroll_util");

// We only need very simple jQuery wrappers for when the

// "real" code wraps html or sets up click handlers.
// We'll simulate most other objects ourselves.
mock_jquery((arg) => {
    if (arg.to_jquery) {
        return arg.to_jquery();
    }

    return {
        addClass() {
            return this;
        },
        replace(regex, string) {
            arg = arg.replace(regex, string);
        },
        html: () => arg,
    };
});

const ListWidget = zrequire("list_widget");

// We build objects here that simulate jQuery containers.
// The main thing to do at first is simulate that our
// scroll container is the nearest ancestor to our main
// container that has a max-height attribute, and then
// the scroll container will have a scroll event attached to
// it.  This is a good time to read set_up_event_handlers
// in the real code.

function make_container() {
    const $container = {};
    $container.attr = noop;
    $container.empty = noop;
    $container.data = noop;

    // Make our append function just set a field we can
    // check in our tests.
    $container.append = ($data) => {
        $container.$appended_data = $data;
    };

    return $container;
}

function make_scroll_container() {
    const $scroll_container = {};

    $scroll_container.cleared = false;

    // Capture the scroll callback so we can call it in
    // our tests.
    $scroll_container.on = (ev, f) => {
        assert.equal(ev, "scroll.list_widget_container");
        $scroll_container.call_scroll = () => {
            f.call($scroll_container);
        };
    };

    $scroll_container.off = (ev) => {
        assert.equal(ev, "scroll.list_widget_container");
        $scroll_container.cleared = true;
    };

    return $scroll_container;
}

function make_sort_container() {
    const $sort_container = {};

    $sort_container.cleared = false;

    $sort_container.on = (ev, sel, f) => {
        assert.equal(ev, "click.list_widget_sort");
        assert.equal(sel, "[data-sort]");
        $sort_container.f = f;
    };

    $sort_container.off = (ev) => {
        assert.equal(ev, "click.list_widget_sort");
        $sort_container.cleared = true;
    };

    return $sort_container;
}

function make_filter_element() {
    const $element = {};

    $element.cleared = false;

    $element.on = (ev, f) => {
        assert.equal(ev, "input.list_widget_filter");
        $element.f = f;
    };

    $element.off = (ev) => {
        assert.equal(ev, "input.list_widget_filter");
        $element.cleared = true;
    };

    return $element;
}

function make_search_input() {
    const $element = {};

    // Allow ourselves to be wrapped by $(...) and
    // return ourselves.
    /* istanbul ignore next */
    $element.to_jquery = () => $element;

    $element.on = (event_name, f) => {
        assert.equal(event_name, "input.list_widget_filter");
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
    return "<div>" + item + "</div>";
}

run_test("scrolling", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    const items = [];

    let get_scroll_element_called = false;
    scroll_util.get_scroll_element = ($element) => {
        get_scroll_element_called = true;
        return $element;
    };

    for (let i = 0; i < 200; i += 1) {
        items.push("item " + i);
    }

    const opts = {
        modifier_html: (item) => item,
        get_item: (item) => item,
        $simplebar_container: $scroll_container,
    };

    ListWidget.create($container, items, opts);

    assert.deepEqual($container.$appended_data.html(), items.slice(0, 80).join(""));
    assert.equal(get_scroll_element_called, true);

    // Set up our fake geometry so it forces a scroll action.
    $scroll_container.scrollTop = 180;
    $scroll_container.clientHeight = 100;
    $scroll_container.scrollHeight = 260;

    // Scrolling gets the next two elements from the list into
    // our widget.
    $scroll_container.call_scroll();
    assert.deepEqual($container.$appended_data.html(), items.slice(80, 100).join(""));
});

run_test("not_scrolling", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    const items = [];

    let get_scroll_element_called = false;
    scroll_util.get_scroll_element = ($element) => {
        get_scroll_element_called = true;
        return $element;
    };

    let post_scroll__pre_render_callback_called = false;
    const post_scroll__pre_render_callback = () => {
        post_scroll__pre_render_callback_called = true;
    };

    let get_min_load_count_called = false;
    const get_min_load_count = (_offset, load_count) => {
        get_min_load_count_called = true;
        return load_count;
    };

    for (let i = 0; i < 200; i += 1) {
        items.push("item " + i);
    }

    const opts = {
        modifier_html: (item) => item,
        get_item: (item) => item,
        $simplebar_container: $scroll_container,
        is_scroll_position_for_render: () => false,
        post_scroll__pre_render_callback,
        get_min_load_count,
    };

    ListWidget.create($container, items, opts);

    assert.deepEqual($container.$appended_data.html(), items.slice(0, 80).join(""));
    assert.equal(get_scroll_element_called, true);

    // Set up our fake geometry.
    $scroll_container.scrollTop = 180;
    $scroll_container.clientHeight = 100;
    $scroll_container.scrollHeight = 260;

    // Since `should_render` is always false, no elements will be
    // added regardless of scrolling.
    $scroll_container.call_scroll();
    // $appended_data remains the same.
    assert.deepEqual($container.$appended_data.html(), items.slice(0, 80).join(""));
    assert.equal(post_scroll__pre_render_callback_called, true);
    assert.equal(get_min_load_count_called, true);
});

run_test("filtering", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    const $search_input = make_search_input();

    let last_filter_value = "";
    const list = ["apple", "banana", "carrot", "dog", "egg", "fence", "grape"];
    const opts = {
        filter: {
            $element: $search_input,
            predicate: (item, value) => item.includes(value),
        },
        modifier_html(item, filter_value) {
            last_filter_value = filter_value;
            return div(item);
        },
        get_item: (item) => item,
        $simplebar_container: $scroll_container,
    };

    const widget = ListWidget.create($container, list, opts);

    let expected_html =
        "<div>apple</div>" +
        "<div>banana</div>" +
        "<div>carrot</div>" +
        "<div>dog</div>" +
        "<div>egg</div>" +
        "<div>fence</div>" +
        "<div>grape</div>";

    assert.deepEqual($container.$appended_data.html(), expected_html);

    // Filtering will pick out dog/egg/grape when we put "g"
    // into our search input.  (This uses the default filter, which
    // is a glorified indexOf call.)
    $search_input.val = () => "g";
    $search_input.simulate_input_event();
    assert.equal(last_filter_value, "g");
    assert.deepEqual(widget.get_current_list(), ["dog", "egg", "grape"]);
    expected_html = "<div>dog</div><div>egg</div><div>grape</div>";
    assert.deepEqual($container.$appended_data.html(), expected_html);

    // We can insert new data into the widget.
    const new_data = ["greta", "faye", "gary", "frank", "giraffe", "fox"];

    widget.replace_list_data(new_data);
    expected_html = "<div>greta</div><div>gary</div><div>giraffe</div>";
    assert.deepEqual($container.$appended_data.html(), expected_html);
});

run_test("no filtering", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    let callback_called = false;
    // Opts does not require a filter key.
    const opts = {
        modifier_html: (item) => div(item),
        $simplebar_container: $scroll_container,
        callback_after_render() {
            callback_called = true;
        },
        get_item: (item) => item,
    };
    const widget = ListWidget.create($container, ["apple", "banana"], opts);
    widget.render();
    assert.deepEqual(callback_called, true);

    const expected_html = "<div>apple</div><div>banana</div>";
    assert.deepEqual($container.$appended_data.html(), expected_html);
});

function sort_button(opts) {
    // The complications here are due to needing to find
    // the list via complicated HTML assumptions. Also, we
    // don't have any abstraction for the button and its
    // siblings other than direct jQuery actions.

    function attr(name) {
        switch (name) {
            case "data-sort":
                return opts.sort_type;
            case "data-sort-prop":
                return opts.prop_name;
            /* istanbul ignore next */
            default:
                throw new Error("unknown attribute: " + name);
        }
    }

    function lookup(sel, value) {
        return (selector) => {
            assert.equal(sel, selector);
            return value;
        };
    }

    const classList = new Set();

    const $button = {
        attr,
        closest: lookup(".progressive-table-wrapper", {
            data: lookup("list-widget", opts.list_name),
        }),
        addClass(cls) {
            classList.add(cls);
        },
        hasClass: (cls) => classList.has(cls),
        removeClass(cls) {
            classList.delete(cls);
        },
        siblings: lookup(".active", {
            removeClass(cls) {
                assert.equal(cls, "active");
                $button.siblings_deactivated = true;
            },
        }),
        siblings_deactivated: false,
        to_jquery: () => $button,
    };

    return $button;
}

run_test("wire up filter element", () => {
    const lst = ["alice", "JESSE", "moses", "scott", "Sean", "Xavier"];

    const $container = make_container();
    const $scroll_container = make_scroll_container();
    const $filter_element = make_filter_element();

    const opts = {
        filter: {
            filterer: (list, value) => list.filter((item) => item.toLowerCase().includes(value)),
            $element: $filter_element,
        },
        modifier_html: (s) => "(" + s + ")",
        get_item: (item) => item,
        $simplebar_container: $scroll_container,
    };

    ListWidget.create($container, lst, opts);
    $filter_element.f.apply({value: "se"});
    assert.equal($container.$appended_data.html(), "(JESSE)(moses)(Sean)");
});

run_test("sorting", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();
    const $sort_container = make_sort_container();

    let cleared;
    $container.empty = () => {
        cleared = true;
    };

    const alice = {name: "alice", salary: 50};
    const bob = {name: "Bob", salary: 40};
    const cal = {name: "cal", salary: 30};
    const dave = {name: "dave", salary: 25};
    const ellen = {name: "ellen", salary: 95};

    const list = [bob, ellen, dave, alice, cal];

    const opts = {
        name: "sorting-list",
        $parent_container: $sort_container,
        modifier_html: (item) => div(item.name) + div(item.salary),
        get_item: (item) => item,
        filter: {
            predicate: () => true,
        },
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["name"]),
            ...ListWidget.generic_sort_functions("numeric", ["salary"]),
        },
        $simplebar_container: $scroll_container,
    };

    function html_for(people) {
        return people.map((item) => opts.modifier_html(item)).join("");
    }

    ListWidget.create($container, list, opts);

    let button_opts;
    let $button;
    let expected_html;

    button_opts = {
        sort_type: "alphabetic",
        prop_name: "name",
        list_name: "my-list",
        active: false,
    };

    $button = sort_button(button_opts);

    $sort_container.f.apply($button);

    assert.ok(cleared);
    assert.ok($button.siblings_deactivated);

    expected_html = html_for([alice, bob, cal, dave, ellen]);
    assert.deepEqual($container.$appended_data.html(), expected_html);

    // Hit same button again to reverse the data.
    cleared = false;
    $sort_container.f.apply($button);
    assert.ok(cleared);
    expected_html = html_for([ellen, dave, cal, bob, alice]);
    assert.deepEqual($container.$appended_data.html(), expected_html);
    assert.ok($button.hasClass("descend"));

    // And then hit a third time to go back to the forward sort.
    cleared = false;
    $sort_container.f.apply($button);
    assert.ok(cleared);
    expected_html = html_for([alice, bob, cal, dave, ellen]);
    assert.deepEqual($container.$appended_data.html(), expected_html);
    assert.ok(!$button.hasClass("descend"));

    // Now try a numeric sort.
    button_opts = {
        sort_type: "numeric",
        prop_name: "salary",
        list_name: "my-list",
        active: false,
    };

    $button = sort_button(button_opts);

    cleared = false;
    $button.siblings_deactivated = false;

    $sort_container.f.apply($button);

    assert.ok(cleared);
    assert.ok($button.siblings_deactivated);

    expected_html = html_for([dave, cal, bob, alice, ellen]);
    assert.deepEqual($container.$appended_data.html(), expected_html);

    // Hit same button again to reverse the numeric sort.
    cleared = false;
    $sort_container.f.apply($button);
    assert.ok(cleared);
    expected_html = html_for([ellen, alice, bob, cal, dave]);
    assert.deepEqual($container.$appended_data.html(), expected_html);
    assert.ok($button.hasClass("descend"));
});

run_test("custom sort", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    const n42 = {x: 6, y: 7};
    const n43 = {x: 1, y: 43};
    const n44 = {x: 4, y: 11};

    const list = [n42, n43, n44];

    function sort_by_x(a, b) {
        return a.x - b.x;
    }

    function sort_by_product(a, b) {
        return a.x * a.y - b.x * b.y;
    }

    const widget = ListWidget.create($container, list, {
        name: "custom-sort-list",
        modifier_html: (n) => "(" + n.x + ", " + n.y + ")",
        get_item: (item) => item,
        sort_fields: {
            product: sort_by_product,
            x_value: sort_by_x,
        },
        init_sort: sort_by_product,
        $simplebar_container: $scroll_container,
    });

    assert.deepEqual($container.$appended_data.html(), "(6, 7)(1, 43)(4, 11)");

    widget.sort("x_value");
    assert.deepEqual($container.$appended_data.html(), "(1, 43)(4, 11)(6, 7)");

    // We can sort without registering the function, too.
    function sort_by_y(a, b) {
        return a.y - b.y;
    }

    widget.sort(sort_by_y);
    assert.deepEqual($container.$appended_data.html(), "(6, 7)(4, 11)(1, 43)");
});

run_test("clear_event_handlers", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();
    const $sort_container = make_sort_container();
    const $filter_element = make_filter_element();

    // We don't care about actual data for this test.
    const list = [];

    const opts = {
        name: "list-we-create-twice",
        $parent_container: $sort_container,
        modifier_html() {},
        get_item() {},
        filter: {
            $element: $filter_element,
            predicate: /* istanbul ignore next */ () => true,
        },
        $simplebar_container: $scroll_container,
    };

    // Create it the first time.
    ListWidget.create($container, list, opts);
    assert.equal($sort_container.cleared, false);
    assert.equal($scroll_container.cleared, false);
    assert.equal($filter_element.cleared, false);

    // The second time we'll clear the old events.
    ListWidget.create($container, list, opts);
    assert.equal($sort_container.cleared, true);
    assert.equal($scroll_container.cleared, true);
    assert.equal($filter_element.cleared, true);
});

run_test("sort helpers", () => {
    /*
        We mostly test our sorting helpers using the
        actual widget, but this test gets us a bit
        more line coverage.
    */
    const alice2 = {name: "alice", id: 2};
    const alice10 = {name: "alice", id: 10};
    const bob2 = {name: "bob", id: 2};
    const bob10 = {name: "bob", id: 10};

    const alpha_cmp = ListWidget.alphabetic_sort("name");
    const num_cmp = ListWidget.numeric_sort("id");

    assert.equal(alpha_cmp(alice2, alice10), 0);
    assert.equal(alpha_cmp(alice2, bob2), -1);
    assert.equal(alpha_cmp(bob2, alice10), 1);
    assert.equal(num_cmp(alice2, bob2), 0);
    assert.equal(num_cmp(alice2, bob10), -1);
    assert.equal(num_cmp(alice10, bob2), 1);
});

run_test("replace_list_data w/filter update", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();

    const list = [1, 2, 3, 4];
    let num_updates = 0;

    const widget = ListWidget.create($container, list, {
        name: "replace-list",
        modifier_html: (n) => "(" + n.toString() + ")",
        get_item: (item) => item,
        filter: {
            predicate: (n) => n % 2 === 0,
            onupdate() {
                num_updates += 1;
            },
        },
        $simplebar_container: $scroll_container,
    });

    assert.equal(num_updates, 0);

    assert.deepEqual($container.$appended_data.html(), "(2)(4)");

    widget.replace_list_data([5, 6, 7, 8]);

    assert.equal(num_updates, 1);

    assert.deepEqual($container.$appended_data.html(), "(6)(8)");
});

run_test("opts.get_item", () => {
    const items = {};

    items[1] = "one";
    items[2] = "two";
    items[3] = "three";
    items[4] = "four";

    const list = [1, 2, 3, 4];

    const boring_opts = {
        get_item: (n) => items[n],
    };

    assert.deepEqual(ListWidget.get_filtered_items("whatever", list, boring_opts), [
        "one",
        "two",
        "three",
        "four",
    ]);

    const predicate = (item, value) => item.startsWith(value);

    const predicate_opts = {
        get_item: (n) => items[n],
        filter: {
            predicate,
        },
    };

    assert.deepEqual(ListWidget.get_filtered_items("t", list, predicate_opts), ["two", "three"]);

    const filterer_opts = {
        get_item: (n) => items[n],
        filter: {
            filterer: (items, value) => items.filter((item) => predicate(item, value)),
        },
    };

    assert.deepEqual(ListWidget.get_filtered_items("t", list, filterer_opts), ["two", "three"]);
});

run_test("render item", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();
    const INITIAL_RENDER_COUNT = 80; // Keep this in sync with the actual code.
    let called = false;
    $scroll_container.find = (element) => {
        const query = element.selector;
        const expected_queries = [
            `tr[data-item='${INITIAL_RENDER_COUNT}']`,
            `tr[data-item='${INITIAL_RENDER_COUNT - 1}']`,
        ];
        const item = INITIAL_RENDER_COUNT - 1;
        const new_html = `<tr data-item=${item}>updated: ${item}</tr>\n`;
        const regex = new RegExp(`\\<tr data-item=${item}\\>.*?<\\/tr\\>`);
        assert.ok(expected_queries.includes(query));
        if (query.includes(`data-item='${INITIAL_RENDER_COUNT}'`)) {
            // This item is not rendered, so we find nothing so return an empty stub.
            return {
                length: 0,
            };
        }
        return {
            // Return a JQuery stub for the original HTML.
            // We want this to be called when we replace
            // the existing HTML with newly rendered HTML.
            replaceWith($element) {
                assert.equal(new_html, $element.html());
                called = true;
                $container.$appended_data.replace(regex, new_html);
            },
            length: 1,
        };
    };

    const list = [...Array.from({length: 100}).keys()];

    let text = "initial";
    const get_item = (item) => ({text: `${text}: ${item}`, value: item});

    const widget = ListWidget.create($container, list, {
        name: "replace-list",
        modifier_html: (item) => `<tr data-item=${item.value}>${item.text}</tr>\n`,
        get_item,
        html_selector: (item) => $(`tr[data-item='${item.value}']`),
        $simplebar_container: $scroll_container,
    });
    const item = INITIAL_RENDER_COUNT - 1;

    assert.ok($container.$appended_data.html().includes("<tr data-item=2>initial: 2</tr>"));
    assert.ok($container.$appended_data.html().includes("<tr data-item=3>initial: 3</tr>"));
    text = "updated";
    called = false;
    widget.render_item(get_item(INITIAL_RENDER_COUNT - 1));
    assert.ok(called);
    assert.ok($container.$appended_data.html().includes("<tr data-item=2>initial: 2</tr>"));
    assert.ok(
        $container.$appended_data.html().includes(`<tr data-item=${item}>updated: ${item}</tr>`),
    );

    // Item 80 should not be in the rendered list. (0 indexed)
    assert.ok(
        !$container.$appended_data
            .html()
            .includes(
                `<tr data-item=${INITIAL_RENDER_COUNT}>initial: ${INITIAL_RENDER_COUNT}</tr>`,
            ),
    );
    called = false;
    widget.render_item(get_item(INITIAL_RENDER_COUNT));
    assert.ok(!called);
    widget.render_item(get_item(INITIAL_RENDER_COUNT - 1));
    assert.ok(called);

    // Tests below this are for the corner cases, where we abort the rerender.

    let get_item_called;
    const widget_2 = ListWidget.create($container, list, {
        name: "replace-list",
        modifier_html: (item) => `<tr data-item=${item.value}>${item.text}</tr>\n`,
        get_item(item) {
            get_item_called = true;
            return item;
        },
        $simplebar_container: $scroll_container,
    });

    get_item_called = false;
    widget_2.render_item(item);
    // Test that we didn't try to render the item.
    assert.ok(!get_item_called);

    let rendering_item = false;
    const widget_3 = ListWidget.create($container, list, {
        name: "replace-list",
        modifier_html: (item) => (rendering_item ? undefined : `${item}\n`),
        get_item,
        html_selector: (item) => $(`tr[data-item='${item}']`),
        $simplebar_container: $scroll_container,
    });
    // Once we have initially rendered the widget, change the
    // behavior of the modifier_html function.
    rendering_item = true;
    blueslip.expect("error", "List item is not a string");
    widget_3.render_item(item);
    blueslip.reset();
});

run_test("Multiselect dropdown retain_selected_items", () => {
    const $container = make_container();
    const $scroll_container = make_scroll_container();
    const $filter_element = make_filter_element();
    let data_rendered = [];

    const list = ["one", "two", "three", "four"].map((x) => ({name: x, value: x}));
    const data = ["one"]; // Data initially selected.

    $container.find = (elem) => DropdownItem(elem);

    // We essentially create fake jQuery functions
    // whose return value are stored in objects so that
    // they can be later asserted with expected values.
    function DropdownItem(element) {
        const temp = {};

        function length() {
            if (element) {
                return true;
            }
            /* istanbul ignore next */
            return false;
        }

        function find(tag) {
            return ListItem(tag, temp);
        }

        function addClass(cls) {
            temp.appended_class = cls;
        }

        temp.element = element;
        return {
            length: length(),
            find,
            addClass,
        };
    }

    function ListItem(element, temp) {
        function expectOne() {
            data_rendered.push(temp);
            return ListItem(element, temp);
        }

        function prepend($data) {
            temp.prepended_data = $data.html();
        }

        return {
            expectOne,
            prepend,
        };
    }

    const widget = ListWidget.create($container, list, {
        name: "replace-list",
        modifier_html: (item) => `<li data-value="${item.value}">${item.name}</li>\n`,
        get_item: (item) => item,
        multiselect: {
            selected_items: data,
        },
        filter: {
            $element: $filter_element,
            predicate: () => true,
        },
        $simplebar_container: $scroll_container,
    });

    const expected_value = [
        {
            element: 'li[data-value="one"]',
            appended_class: "checked",
            prepended_data: "<i>",
        },
    ];

    assert.deepEqual(expected_value, data_rendered);

    // Reset the variable and re execute the `widget.render` method.
    data_rendered = [];

    // Making sure!
    assert.deepEqual(data_rendered, []);

    widget.hard_redraw();

    // Expect the `data_rendered` array to be same again.
    assert.deepEqual(expected_value, data_rendered);
});
