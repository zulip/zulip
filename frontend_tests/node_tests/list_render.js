"use strict";

zrequire("list_render");

// We need these stubs to get by instanceof checks.
// The list_render library allows you to insert objects
// that are either jQuery, Element, or just raw HTML
// strings.  We initially test with raw strings.
set_global("jQuery", "stub");
function Element() {
    return {};
}
set_global("Element", Element);
set_global("ui", {});

// We only need very simple jQuery wrappers for when the
// "real" code wraps html or sets up click handlers.
// We'll simulate most other objects ourselves.
set_global("$", (arg) => {
    if (arg.to_jquery) {
        return arg.to_jquery();
    }

    return {
        replace: (regex, string) => {
            arg = arg.replace(regex, string);
        },
        html: () => arg,
    };
});

// We build objects here that simulate jQuery containers.
// The main thing to do at first is simulate that our
// scroll container is the nearest ancestor to our main
// container that has a max-height attribute, and then
// the scroll container will have a scroll event attached to
// it.  This is a good time to read set_up_event_handlers
// in the real code.

function make_container() {
    const container = {};

    container.length = () => 1;
    container.is = () => false;
    container.css = (prop) => {
        assert.equal(prop, "max-height");
        return "none";
    };

    // Make our append function just set a field we can
    // check in our tests.
    container.append = (data) => {
        container.appended_data = data;
    };

    return container;
}

function make_scroll_container() {
    const scroll_container = {};

    scroll_container.cleared = false;

    // Capture the scroll callback so we can call it in
    // our tests.
    scroll_container.on = (ev, f) => {
        assert.equal(ev, "scroll.list_widget_container");
        scroll_container.call_scroll = () => {
            f.call(scroll_container);
        };
    };

    scroll_container.off = (ev) => {
        assert.equal(ev, "scroll.list_widget_container");
        scroll_container.cleared = true;
    };

    return scroll_container;
}

function make_sort_container() {
    const sort_container = {};

    sort_container.cleared = false;

    sort_container.on = (ev, sel, f) => {
        assert.equal(ev, "click.list_widget_sort");
        assert.equal(sel, "[data-sort]");
        sort_container.f = f;
    };

    sort_container.off = (ev) => {
        assert.equal(ev, "click.list_widget_sort");
        sort_container.cleared = true;
    };

    return sort_container;
}

function make_filter_element() {
    const element = {};

    element.cleared = false;

    element.on = (ev, f) => {
        assert.equal(ev, "input.list_widget_filter");
        element.f = f;
    };

    element.off = (ev) => {
        assert.equal(ev, "input.list_widget_filter");
        element.cleared = true;
    };

    return element;
}

function make_search_input() {
    const $element = {};

    // Allow ourselves to be wrapped by $(...) and
    // return ourselves.
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
    const container = make_container();
    const scroll_container = make_scroll_container();

    const items = [];

    let get_scroll_element_called = false;
    ui.get_scroll_element = (element) => {
        get_scroll_element_called = true;
        return element;
    };

    for (let i = 0; i < 200; i += 1) {
        items.push("item " + i);
    }

    const opts = {
        modifier: (item) => item,
        simplebar_container: scroll_container,
    };

    container.html = (html) => {
        assert.equal(html, "");
    };
    list_render.create(container, items, opts);

    assert.deepEqual(container.appended_data.html(), items.slice(0, 80).join(""));
    assert.equal(get_scroll_element_called, true);

    // Set up our fake geometry so it forces a scroll action.
    scroll_container.scrollTop = 180;
    scroll_container.clientHeight = 100;
    scroll_container.scrollHeight = 260;

    // Scrolling gets the next two elements from the list into
    // our widget.
    scroll_container.call_scroll();
    assert.deepEqual(container.appended_data.html(), items.slice(80, 100).join(""));
});

run_test("filtering", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();

    const search_input = make_search_input();

    const list = ["apple", "banana", "carrot", "dog", "egg", "fence", "grape"];
    const opts = {
        filter: {
            element: search_input,
            predicate: (item, value) => item.includes(value),
        },
        modifier: (item) => div(item),
        simplebar_container: scroll_container,
    };

    container.html = (html) => {
        assert.equal(html, "");
    };
    const widget = list_render.create(container, list, opts);

    let expected_html =
        "<div>apple</div>" +
        "<div>banana</div>" +
        "<div>carrot</div>" +
        "<div>dog</div>" +
        "<div>egg</div>" +
        "<div>fence</div>" +
        "<div>grape</div>";

    assert.deepEqual(container.appended_data.html(), expected_html);

    // Filtering will pick out dog/egg/grape when we put "g"
    // into our search input.  (This uses the default filter, which
    // is a glorified indexOf call.)
    search_input.val = () => "g";
    search_input.simulate_input_event();
    expected_html = "<div>dog</div><div>egg</div><div>grape</div>";
    assert.deepEqual(container.appended_data.html(), expected_html);

    // We can insert new data into the widget.
    const new_data = ["greta", "faye", "gary", "frank", "giraffe", "fox"];

    widget.replace_list_data(new_data);
    expected_html = "<div>greta</div><div>gary</div><div>giraffe</div>";
    assert.deepEqual(container.appended_data.html(), expected_html);
});

run_test("no filtering", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    container.html = () => {};

    // Opts does not require a filter key.
    const opts = {
        modifier: (item) => div(item),
        simplebar_container: scroll_container,
    };
    const widget = list_render.create(container, ["apple", "banana"], opts);
    widget.render();

    const expected_html = "<div>apple</div><div>banana</div>";
    assert.deepEqual(container.appended_data.html(), expected_html);
});

function sort_button(opts) {
    // The complications here are due to needing to find
    // the list via complicated HTML assumptions. Also, we
    // don't have any abstraction for the button and its
    // siblings other than direct jQuery actions.

    function data(sel) {
        switch (sel) {
            case "sort":
                return opts.sort_type;
            case "sort-prop":
                return opts.prop_name;
            default:
                throw new Error("unknown selector: " + sel);
        }
    }

    function lookup(sel, value) {
        return (selector) => {
            assert.equal(sel, selector);
            return value;
        };
    }

    const classList = new Set();

    const button = {
        data,
        closest: lookup(".progressive-table-wrapper", {
            data: lookup("list-render", opts.list_name),
        }),
        addClass: (cls) => {
            classList.add(cls);
        },
        hasClass: (cls) => classList.has(cls),
        removeClass: (cls) => {
            classList.delete(cls);
        },
        siblings: lookup(".active", {
            removeClass: (cls) => {
                assert.equal(cls, "active");
                button.siblings_deactivated = true;
            },
        }),
        siblings_deactivated: false,
        to_jquery: () => button,
    };

    return button;
}

run_test("wire up filter element", () => {
    const lst = ["alice", "JESSE", "moses", "scott", "Sean", "Xavier"];

    const container = make_container();
    const scroll_container = make_scroll_container();
    const filter_element = make_filter_element();

    // We don't care about what gets drawn initially.
    container.html = () => {};

    const opts = {
        filter: {
            filterer: (list, value) => list.filter((item) => item.toLowerCase().includes(value)),
            element: filter_element,
        },
        modifier: (s) => "(" + s + ")",
        simplebar_container: scroll_container,
    };

    list_render.create(container, lst, opts);
    filter_element.f.apply({value: "se"});
    assert.equal(container.appended_data.html(), "(JESSE)(moses)(Sean)");
});

run_test("sorting", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    const sort_container = make_sort_container();

    let cleared;
    container.html = (html) => {
        assert.equal(html, "");
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
        parent_container: sort_container,
        modifier: (item) => div(item.name) + div(item.salary),
        filter: {
            predicate: () => true,
        },
        simplebar_container: scroll_container,
    };

    function html_for(people) {
        return people.map(opts.modifier).join("");
    }

    list_render.create(container, list, opts);

    let button_opts;
    let button;
    let expected_html;

    button_opts = {
        sort_type: "alphabetic",
        prop_name: "name",
        list_name: "my-list",
        active: false,
    };

    button = sort_button(button_opts);

    sort_container.f.apply(button);

    assert(cleared);
    assert(button.siblings_deactivated);

    expected_html = html_for([alice, bob, cal, dave, ellen]);
    assert.deepEqual(container.appended_data.html(), expected_html);

    // Hit same button again to reverse the data.
    cleared = false;
    sort_container.f.apply(button);
    assert(cleared);
    expected_html = html_for([ellen, dave, cal, bob, alice]);
    assert.deepEqual(container.appended_data.html(), expected_html);
    assert(button.hasClass("descend"));

    // And then hit a third time to go back to the forward sort.
    cleared = false;
    sort_container.f.apply(button);
    assert(cleared);
    expected_html = html_for([alice, bob, cal, dave, ellen]);
    assert.deepEqual(container.appended_data.html(), expected_html);
    assert(!button.hasClass("descend"));

    // Now try a numeric sort.
    button_opts = {
        sort_type: "numeric",
        prop_name: "salary",
        list_name: "my-list",
        active: false,
    };

    button = sort_button(button_opts);

    cleared = false;
    button.siblings_deactivated = false;

    sort_container.f.apply(button);

    assert(cleared);
    assert(button.siblings_deactivated);

    expected_html = html_for([dave, cal, bob, alice, ellen]);
    assert.deepEqual(container.appended_data.html(), expected_html);

    // Hit same button again to reverse the numeric sort.
    cleared = false;
    sort_container.f.apply(button);
    assert(cleared);
    expected_html = html_for([ellen, alice, bob, cal, dave]);
    assert.deepEqual(container.appended_data.html(), expected_html);
    assert(button.hasClass("descend"));
});

run_test("custom sort", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    container.html = () => {};

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

    list_render.create(container, list, {
        name: "custom-sort-list",
        modifier: (n) => "(" + n.x + ", " + n.y + ")",
        sort_fields: {
            product: sort_by_product,
            x_value: sort_by_x,
        },
        init_sort: [sort_by_product],
        simplebar_container: scroll_container,
    });

    assert.deepEqual(container.appended_data.html(), "(6, 7)(1, 43)(4, 11)");

    const widget = list_render.get("custom-sort-list");

    widget.sort("x_value");
    assert.deepEqual(container.appended_data.html(), "(1, 43)(4, 11)(6, 7)");

    // We can sort without registering the function, too.
    function sort_by_y(a, b) {
        return a.y - b.y;
    }

    widget.sort(sort_by_y);
    assert.deepEqual(container.appended_data.html(), "(6, 7)(4, 11)(1, 43)");
});

run_test("clear_event_handlers", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    const sort_container = make_sort_container();
    const filter_element = make_filter_element();

    // We don't care about actual data for this test.
    const list = [];
    container.html = () => {};

    const opts = {
        name: "list-we-create-twice",
        parent_container: sort_container,
        modifier: () => {},
        filter: {
            element: filter_element,
            predicate: () => true,
        },
        simplebar_container: scroll_container,
    };

    // Create it the first time.
    list_render.create(container, list, opts);
    assert.equal(sort_container.cleared, false);
    assert.equal(scroll_container.cleared, false);
    assert.equal(filter_element.cleared, false);

    // The second time we'll clear the old events.
    list_render.create(container, list, opts);
    assert.equal(sort_container.cleared, true);
    assert.equal(scroll_container.cleared, true);
    assert.equal(filter_element.cleared, true);
});

run_test("errors", () => {
    // We don't care about actual data for this test.
    const list = ["stub"];
    const container = make_container();
    const scroll_container = make_scroll_container();

    blueslip.expect("error", "Need opts to create widget.");
    list_render.create(container, list);
    blueslip.reset();

    blueslip.expect("error", "simplebar_container is missing.");
    list_render.create(container, list, {
        modifier: "hello world",
    });
    blueslip.reset();

    blueslip.expect("error", "get_item should be a function");
    list_render.create(container, list, {
        get_item: "not a function",
        simplebar_container: scroll_container,
    });
    blueslip.reset();

    blueslip.expect("error", "Filter predicate is not a function.");
    list_render.create(container, list, {
        filter: {
            predicate: "wrong type",
        },
        simplebar_container: scroll_container,
    });
    blueslip.reset();

    blueslip.expect("error", "Filterer and predicate are mutually exclusive.");
    list_render.create(container, list, {
        filter: {
            filterer: () => true,
            predicate: () => true,
        },
        simplebar_container: scroll_container,
    });
    blueslip.reset();

    blueslip.expect("error", "Filter filterer is not a function (or missing).");
    list_render.create(container, list, {
        filter: {},
        simplebar_container: scroll_container,
    });
    blueslip.reset();

    container.html = () => {};
    blueslip.expect("error", "List item is not a string: 999");
    list_render.create(container, list, {
        modifier: () => 999,
        simplebar_container: scroll_container,
    });
    blueslip.reset();
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

    const alpha_cmp = list_render.alphabetic_sort("name");
    const num_cmp = list_render.numeric_sort("id");

    assert.equal(alpha_cmp(alice2, alice10), 0);
    assert.equal(alpha_cmp(alice2, bob2), -1);
    assert.equal(alpha_cmp(bob2, alice10), 1);
    assert.equal(num_cmp(alice2, bob2), 0);
    assert.equal(num_cmp(alice2, bob10), -1);
    assert.equal(num_cmp(alice10, bob2), 1);
});

run_test("replace_list_data w/filter update", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    container.html = () => {};

    const list = [1, 2, 3, 4];
    let num_updates = 0;

    list_render.create(container, list, {
        name: "replace-list",
        modifier: (n) => "(" + n.toString() + ")",
        filter: {
            predicate: (n) => n % 2 === 0,
            onupdate: () => {
                num_updates += 1;
            },
        },
        simplebar_container: scroll_container,
    });

    assert.equal(num_updates, 0);

    assert.deepEqual(container.appended_data.html(), "(2)(4)");

    const widget = list_render.get("replace-list");
    widget.replace_list_data([5, 6, 7, 8]);

    assert.equal(num_updates, 1);

    assert.deepEqual(container.appended_data.html(), "(6)(8)");
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

    assert.deepEqual(list_render.get_filtered_items("whatever", list, boring_opts), [
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

    assert.deepEqual(list_render.get_filtered_items("t", list, predicate_opts), ["two", "three"]);

    const filterer_opts = {
        get_item: (n) => items[n],
        filter: {
            filterer: (items, value) => items.filter((item) => predicate(item, value)),
        },
    };

    assert.deepEqual(list_render.get_filtered_items("t", list, filterer_opts), ["two", "three"]);
});

run_test("render item", () => {
    const container = make_container();
    const scroll_container = make_scroll_container();
    const INITIAL_RENDER_COUNT = 80; // Keep this in sync with the actual code.
    container.html = () => {};
    let called = false;
    scroll_container.find = (query) => {
        const expected_queries = [
            `tr[data-item='${INITIAL_RENDER_COUNT}']`,
            `tr[data-item='${INITIAL_RENDER_COUNT - 1}']`,
        ];
        const item = INITIAL_RENDER_COUNT - 1;
        const new_html = `<tr data-item=${item}>updated: ${item}</tr>\n`;
        const regex = new RegExp(`\\<tr data-item=${item}\\>.*?<\\/tr\\>`);
        assert(expected_queries.includes(query));
        if (query.includes(`data-item='${INITIAL_RENDER_COUNT}'`)) {
            return undefined; // This item is not rendered, so we find nothing
        }
        return {
            // Return a JQuery stub for the original HTML.
            // We want this to be called when we replace
            // the existing HTML with newly rendered HTML.
            replaceWith: (html) => {
                assert.equal(new_html, html);
                called = true;
                container.appended_data.replace(regex, new_html);
            },
        };
    };

    const list = [...new Array(100).keys()];

    let text = "initial";
    const get_item = (item) => ({text: `${text}: ${item}`, value: item});

    const widget = list_render.create(container, list, {
        name: "replace-list",
        modifier: (item) => `<tr data-item=${item.value}>${item.text}</tr>\n`,
        get_item,
        html_selector: (item) => `tr[data-item='${item}']`,
        simplebar_container: scroll_container,
    });
    const item = INITIAL_RENDER_COUNT - 1;

    assert(container.appended_data.html().includes("<tr data-item=2>initial: 2</tr>"));
    assert(container.appended_data.html().includes("<tr data-item=3>initial: 3</tr>"));
    text = "updated";
    called = false;
    widget.render_item(INITIAL_RENDER_COUNT - 1);
    assert(called);
    assert(container.appended_data.html().includes("<tr data-item=2>initial: 2</tr>"));
    assert(container.appended_data.html().includes(`<tr data-item=${item}>updated: ${item}</tr>`));

    // Item 80 should not be in the rendered list. (0 indexed)
    assert(
        !container.appended_data
            .html()
            .includes(
                `<tr data-item=${INITIAL_RENDER_COUNT}>initial: ${INITIAL_RENDER_COUNT}</tr>`,
            ),
    );
    called = false;
    widget.render_item(INITIAL_RENDER_COUNT);
    assert(!called);
    widget.render_item(INITIAL_RENDER_COUNT - 1);
    assert(called);

    // Tests below this are for the corner cases, where we abort the rerender.

    blueslip.expect("error", "html_selector should be a function.");
    list_render.create(container, list, {
        name: "replace-list",
        modifier: (item) => `<tr data-item=${item.value}>${item.text}</tr>\n`,
        get_item,
        html_selector: "hello world",
        simplebar_container: scroll_container,
    });
    blueslip.reset();

    let get_item_called;
    const widget_2 = list_render.create(container, list, {
        name: "replace-list",
        modifier: (item) => `<tr data-item=${item.value}>${item.text}</tr>\n`,
        get_item: (item) => {
            get_item_called = true;
            return item;
        },
        simplebar_container: scroll_container,
    });
    get_item_called = false;
    widget_2.render_item(item);
    // Test that we didn't try to render the item.
    assert(!get_item_called);

    let rendering_item = false;
    const widget_3 = list_render.create(container, list, {
        name: "replace-list",
        modifier: (item) => (rendering_item ? undefined : `${item}\n`),
        get_item,
        html_selector: (item) => `tr[data-item='${item}']`,
        simplebar_container: scroll_container,
    });
    // Once we have initially rendered the widget, change the
    // behavior of the modifier function.
    rendering_item = true;
    blueslip.expect("error", "List item is not a string: undefined");
    widget_3.render_item(item);
    blueslip.reset();
});
