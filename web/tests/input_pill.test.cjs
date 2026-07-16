"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

set_global("document", {
    // Reports the caret as being at the end of a pill's edit box.
    createRange: () => ({
        selectNodeContents: noop,
        setStart: noop,
        toString: () => "",
    }),
});
class ClipboardEvent {}
set_global("ClipboardEvent", ClipboardEvent);

mock_esm("../src/ui_util", {
    place_caret_at_end: noop,
});

set_global("getSelection", () => ({
    anchorOffset: 0,
    rangeCount: 1,
    getRangeAt: () => ({endContainer: {}, endOffset: 0}),
    toString() {
        return "";
    },
}));

// The blur-commit of a pill edit is deferred, so tests run it explicitly.
let deferred_callbacks = [];
set_global("setTimeout", (f) => {
    deferred_callbacks.push(f);
});

function run_deferred_callbacks() {
    const callbacks = deferred_callbacks;
    deferred_callbacks = [];
    for (const callback of callbacks) {
        callback();
    }
}

const input_pill = zrequire("input_pill");

function pill_html(value) {
    const opts = {
        display_value: value,
    };
    return require("../templates/input_pill.hbs")(opts);
}

run_test("basics", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(data.display_value, "JavaScript");
        return html;
    });

    const $pill_input = $.create("pill_input");
    const $container = $.create("container");
    $container.set_find_results(".input", $pill_input);

    const widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: (item) => item.language,
    });

    // type for a pill can be any string but it needs to be
    // defined while creating any pill.
    const item = {
        language: "JavaScript",
        type: "language",
    };

    let inserted_before;
    const expected_html = pill_html("JavaScript");

    $pill_input[0].before = (element) => {
        inserted_before = true;
        assert.equal(element.innerHTML, expected_html);
    };

    widget.appendValidatedData(item);
    assert.ok(!widget.is_pending());
    assert.ok(inserted_before);

    assert.deepEqual(widget.items(), [item]);
});

function set_up() {
    const items = {
        blue: {
            color_name: "BLUE",
            description: "color of the sky",
            type: "color",
        },

        red: {
            color_name: "RED",
            type: "color",
            description: "color of stop signs",
        },

        yellow: {
            color_name: "YELLOW",
            type: "color",
            description: "color of bananas",
        },
    };

    const $pill_input = $.create("pill_input");
    $pill_input[0].before = noop;

    const create_item_from_text = (text) => items[text];

    const $container = $.create("container");
    $container.set_find_results(".input", $pill_input);

    const config = {
        $container,
        create_item_from_text,
        get_text_from_item: (item) => item.color_name,
        get_display_value_from_item: (item) => item.color_name,
    };

    return {
        config,
        $pill_input,
        items,
        $container,
    };
}

run_test("copy from pill", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.ok(["BLUE", "RED"].includes(data.display_value));
        return html;
    });

    const info = set_up();
    const config = info.config;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    const copy_handler = $container.get_on_handler("copy", ".pill");

    let copied_text;

    const pill_stub = $(pill_html("RED"))[0];

    const originalEvent = new ClipboardEvent();
    originalEvent.clipboardData = {
        setData(format, text) {
            assert.equal(format, "text/plain");
            copied_text = text;
        },
    };
    const e = {
        originalEvent,
        preventDefault: noop,
    };

    copy_handler.call(pill_stub, e);

    assert.equal(copied_text, "RED");
});

run_test("paste to input", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (_data, html) => html);

    const info = set_up();
    const config = {...info.config, show_outline_on_invalid_input: true};
    const $container = info.$container;
    const $pill_input = info.$pill_input;
    const items = info.items;

    const widget = input_pill.create(config);

    const paste_handler = $container.get_on_handler("paste", ".input");

    let paste_text = "blue,yellow";

    const originalEvent = new ClipboardEvent();
    originalEvent.clipboardData = {
        getData(format) {
            assert.equal(format, "text/plain");
            return paste_text;
        },
    };
    const e = {
        originalEvent,
        preventDefault: noop,
    };

    document.execCommand = (cmd, _, text) => {
        assert.equal(cmd, "insertText");
        $container.find(".input").text(text);
    };

    paste_handler(e);

    assert.deepEqual(widget.items(), [items.blue, items.yellow]);

    // Pasted text that doesn't form a valid pill stays in the input,
    // without the shake animation or the invalid outline.
    paste_text = "red,purple";
    paste_handler(e);

    assert.deepEqual(widget.items(), [items.blue, items.yellow, items.red]);
    assert.equal($pill_input.text(), "purple");
    assert.ok(!$pill_input.hasClass("input-validation-shake"));
    assert.ok(!$container.hasClass("invalid"));

    let entered = false;
    widget.createPillonPaste(() => {
        entered = true;
    });

    paste_handler(e);
    assert.ok(entered);
});

run_test("paste invalid text with shake_on_invalid_paste", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (_data, html) => html);

    const info = set_up();
    const config = {
        ...info.config,
        show_outline_on_invalid_input: true,
        shake_on_invalid_paste: true,
    };
    const $container = info.$container;
    const $pill_input = info.$pill_input;
    const items = info.items;

    const widget = input_pill.create(config);

    const paste_handler = $container.get_on_handler("paste", ".input");

    const originalEvent = new ClipboardEvent();
    originalEvent.clipboardData = {
        getData: () => "red,purple",
    };
    const e = {
        originalEvent,
        preventDefault: noop,
    };

    document.execCommand = (_cmd, _, text) => {
        $container.find(".input").text(text);
    };

    paste_handler(e);

    assert.deepEqual(widget.items(), [items.red]);
    assert.equal($pill_input.text(), "purple");
    assert.ok($pill_input.hasClass("input-validation-shake"));
    assert.ok($container.hasClass("invalid"));
});

run_test("arrows on pills", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (_data, html) => html);

    const info = set_up();
    const config = info.config;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    const key_handler = $container.get_on_handler("keydown", ".pill");

    function test_key(c) {
        key_handler({
            key: c,
        });
    }

    const $prev_pill_stub = $.create("prev-pill-stub");
    const $next_pill_stub = $.create("next-pill-stub");
    const $pill_stub = $.create("pill-stub");
    $pill_stub.set_prev($prev_pill_stub);
    $pill_stub.set_next($next_pill_stub);

    $container.set_find_results(".pill:focus", $pill_stub);

    // We use the same stub to test both arrows, since we don't
    // actually cause any real state changes here.  We stub out
    // the only interaction, which is to move the focus.
    test_key("ArrowLeft");
    assert.ok($prev_pill_stub.is(":focus"));

    test_key("ArrowRight");
    assert.ok($next_pill_stub.is(":focus"));
});

run_test("left arrow on input", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();
    const config = info.config;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    const key_handler = $container.get_on_handler("keydown", ".input");

    const $pill_stub = $.create("pill-stub");
    $container.set_find_results(".pill", $pill_stub);

    key_handler({
        key: "ArrowLeft",
    });

    assert.ok($pill_stub.is(":focus"));
});

run_test("comma", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();
    const config = info.config;
    const items = info.items;
    const $pill_input = info.$pill_input;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    assert.deepEqual(widget.items(), [items.blue, items.red]);

    const key_handler = $container.get_on_handler("keydown", ".input");

    $pill_input.text(" yel");

    key_handler({
        key: ",",
        preventDefault: noop,
    });

    assert.deepEqual(widget.items(), [items.blue, items.red]);
    assert.ok($pill_input.hasClass("input-validation-shake"));

    $pill_input.text(" yellow");

    key_handler({
        key: ",",
        preventDefault: noop,
    });

    assert.deepEqual(widget.items(), [items.blue, items.red, items.yellow]);
});

run_test("Enter key with text", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();
    const config = info.config;
    const items = info.items;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    assert.deepEqual(widget.items(), [items.blue, items.red]);

    const key_handler = $container.get_on_handler("keydown", ".input");

    key_handler.call(
        {
            textContent: " yellow ",
        },
        {
            key: "Enter",
            preventDefault: noop,
            stopPropagation: noop,
        },
    );

    assert.deepEqual(widget.items(), [items.blue, items.red, items.yellow]);
});

run_test("insert_remove", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        assert.ok(html.startsWith, "<div class='pill'");
        return html;
    });

    const info = set_up();

    const config = info.config;
    const $pill_input = info.$pill_input;
    const items = info.items;
    const $container = info.$container;

    const inserted_html = [];
    $pill_input[0].before = (element) => {
        inserted_html.push(element.innerHTML);
    };

    const widget = input_pill.create(config);

    let created;
    let removed;

    widget.onPillCreate(() => {
        created = true;
    });

    widget.onPillRemove(() => {
        removed = true;
    });

    widget.appendValue("blue,chartreuse,red,yellow,mauve");

    assert.ok(created);
    assert.ok(!removed);

    assert.deepEqual(inserted_html, [pill_html("BLUE"), pill_html("RED"), pill_html("YELLOW")]);

    assert.deepEqual(widget.items(), [items.blue, items.red, items.yellow]);

    assert.equal($pill_input.text(), "chartreuse, mauve");

    assert.equal(widget.is_pending(), true);
    widget.clear_text();
    assert.equal($pill_input.text(), "");
    assert.equal(widget.is_pending(), false);

    let color_removed;
    function set_colored_removed_func(color) {
        return () => {
            color_removed = color;
        };
    }

    let color_focused;
    function handle_event(color) {
        return () => {
            color_focused = color;
        };
    }

    const pills = widget._get_pills_for_testing();
    for (const pill of pills) {
        pill.$element[0].remove = set_colored_removed_func(pill.item.color_name);
        pill.$element.on("focus", handle_event(pill.item.color_name));
    }

    let key_handler = $container.get_on_handler("keydown", ".input");

    key_handler.call(
        {
            textContent: "",
        },
        {
            key: "Backspace",
            preventDefault: noop,
        },
    );

    // The first backspace focuses the pill, the second removes it.
    assert.ok(!removed);
    assert.equal(color_focused, "YELLOW");
    const yellow_pill = pills.find((pill) => pill.item.color_name === "YELLOW");
    $container.set_find_results(".pill:focus", yellow_pill.$element);

    key_handler = $container.get_on_handler("keydown", ".pill");
    key_handler.call(
        {},
        {
            key: "Backspace",
            preventDefault: noop,
        },
    );
    assert.ok(removed);
    assert.equal(color_removed, "YELLOW");
    assert.ok($pill_input.is(":focus"));
    color_removed = undefined;

    $pill_input.trigger("blur");
    assert.deepEqual(widget.items(), [items.blue, items.red]);

    const red_pill = pills.find((pill) => pill.item.color_name === "RED");
    $container.set_find_results(".pill:focus", red_pill.$element);

    // Disabled pill should not be removed, and focus moves to the
    // previous pill instead of the input.
    red_pill.disabled = true;
    const $prev_pill_stub = $("<prev-stub>");
    red_pill.$element.set_prev($prev_pill_stub);

    key_handler = $container.get_on_handler("keydown", ".pill");
    key_handler({
        key: "Backspace",
        preventDefault: noop,
    });

    assert.equal(color_removed, undefined);
    assert.ok($prev_pill_stub.is(":focus"));
    assert.ok(!$pill_input.is(":focus"));

    // We should be able to remove the pill after marking it as not
    // disabled.
    red_pill.disabled = false;
    $prev_pill_stub.trigger("blur");
    assert.deepEqual(widget.items(), [items.blue, items.red]);

    key_handler({
        key: "Backspace",
        preventDefault: noop,
    });
    assert.equal(color_removed, "RED");
    assert.ok($pill_input.is(":focus"));
    assert.deepEqual(widget.items(), [items.blue]);
    color_removed = undefined;

    // A disabled first pill has no previous pill, so focus stays on it.
    $pill_input.trigger("blur");
    const blue_pill = pills.find((pill) => pill.item.color_name === "BLUE");
    blue_pill.disabled = true;
    blue_pill.$element[0].previousElementSibling = null;
    blue_pill.$element.trigger("focus");
    $container.set_find_results(".pill:focus", blue_pill.$element);

    key_handler({
        key: "Backspace",
        preventDefault: noop,
    });
    assert.equal(color_removed, undefined);
    assert.ok(blue_pill.$element.is(":focus"));
    assert.ok(!$pill_input.is(":focus"));
    assert.deepEqual(widget.items(), [items.blue]);
});

run_test("exit button on pill", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        assert.ok(html.startsWith, "<div class='pill'");
        return html;
    });

    const info = set_up();

    const config = info.config;
    const items = info.items;
    const $container = info.$container;

    const widget = input_pill.create(config);

    widget.appendValue("blue,red");

    const pills = widget._get_pills_for_testing();
    for (const pill of pills) {
        pill.$element[0].remove = noop;
    }

    const $curr_pill_stub = {
        [0]: $(pill_html("BLUE"))[0],
        length: 1,
    };

    const exit_button_stub = {
        to_$: () => ({
            closest(sel) {
                assert.equal(sel, ".pill");
                return $curr_pill_stub;
            },
        }),
    };

    const e = {
        stopPropagation: noop,
    };
    const exit_click_handler = $container.get_on_handler("click", ".exit");

    exit_click_handler.call(exit_button_stub, e);

    assert.deepEqual(widget.items(), [items.red]);
});

run_test("misc things", () => {
    const info = set_up();

    const $container = info.$container;
    const $pill_input = info.$pill_input;
    input_pill.create(info.config);

    // animation
    const animation_end_handler = $container.get_on_handler("animationend", ".input, .pill");

    let shake_class_removed = false;

    const input_stub = {
        to_$: () => ({
            removeClass(cls) {
                assert.equal(cls, "input-validation-shake");
                shake_class_removed = true;
            },
        }),
    };

    animation_end_handler.call(input_stub);
    assert.ok(shake_class_removed);

    // click on container
    const container_click_handler = $container.get_on_handler("click");

    const $stub = $.create("the-pill-container");
    $stub.set_find_results(".input", $pill_input);
    $stub.set_matches(".pill-container", true);

    const this_ = {
        to_$: () => $stub,
    };

    container_click_handler.call(this_, {target: this_});
});

run_test("appendValue/clear", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        assert.ok(html.startsWith, "<div class='pill'");
        return html;
    });

    const $pill_input = $.create("pill_input");
    const $container = $.create("container");
    $container.set_find_results(".input", $pill_input);

    const config = {
        $container,
        create_item_from_text: (s) => ({type: "color", color_name: s}),
        get_text_from_item: /* istanbul ignore next */ (s) => s.color_name,
        get_display_value_from_item: (s) => s.color_name,
    };

    $pill_input[0].before = noop;

    const widget = input_pill.create(config);

    // First test some early-exit code.
    widget.appendValue("");
    assert.deepEqual(widget._get_pills_for_testing(), []);

    // Now set up real data.
    widget.appendValue("red,yellow,blue");

    const pills = widget._get_pills_for_testing();

    const removed_colors = [];
    for (const pill of pills) {
        pill.$element[0].remove = () => {
            removed_colors.push(pill.item.color_name);
        };
    }

    widget.clear();

    // Note that we remove colors in the reverse order that we inserted.
    assert.deepEqual(removed_colors, ["blue", "yellow", "red"]);
    assert.equal($pill_input[0].textContent, "");
});

run_test("getCurrentText", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();
    const config = info.config;
    const items = info.items;
    const $pill_input = info.$pill_input;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");
    assert.deepEqual(widget.items(), [items.blue, items.red]);

    $pill_input.text("yellow");
    assert.equal(widget.getCurrentText(), "yellow");

    const key_handler = $container.get_on_handler("keydown", ".input");
    key_handler({
        key: " ",
        preventDefault: noop,
    });
    key_handler({
        key: ",",
        preventDefault: noop,
    });

    assert.deepEqual(widget.items(), [items.blue, items.red, items.yellow]);
});

run_test("onTextInputHook", () => {
    const info = set_up();
    const config = info.config;
    const widget = input_pill.create(config);
    const $container = info.$container;
    const $pill_input = info.$pill_input;

    let hookCalled = false;
    let currentText = "re";
    const onTextInputHook = () => {
        hookCalled = true;

        // Test that the hook always gets the correct updated text.
        assert.equal(widget.getCurrentText(), currentText);
    };

    widget.onTextInputHook(onTextInputHook);

    const input_handler = $container.get_on_handler("input", ".input");

    $pill_input.text(currentText);
    input_handler();

    currentText += "d";
    $pill_input.text(currentText);
    input_handler();

    assert.ok(hookCalled);
});

run_test("getPillByPredicate", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();

    const widget = input_pill.create(info.config);
    widget.appendValue("blue,red,yellow");

    // Test finding pill by color name
    const found_blue_pill = widget.getPillByPredicate((item) => item.color_name === "BLUE");
    assert.ok(found_blue_pill);
    assert.equal(found_blue_pill.item.color_name, "BLUE");
    assert.equal(found_blue_pill.item.description, "color of the sky");

    const found_red_pill = widget.getPillByPredicate((item) => item.color_name === "RED");
    assert.ok(found_red_pill);
    assert.equal(found_red_pill.item.color_name, "RED");
    assert.equal(found_red_pill.item.description, "color of stop signs");

    // Test with non-existent item returns undefined
    const nonexistent_pill = widget.getPillByPredicate((item) => item.color_name === "GREEN");
    assert.equal(nonexistent_pill, undefined);

    // Test finding pill by different property (description)
    const found_by_description = widget.getPillByPredicate(
        (item) => item.description === "color of the sky",
    );
    assert.ok(found_by_description);
    assert.equal(found_by_description.item.color_name, "BLUE");
});

run_test("updatePill", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        return html;
    });

    const info = set_up();

    const widget = input_pill.create(info.config);
    widget.appendValue("blue,red");

    const pills = widget._get_pills_for_testing();
    assert.equal(pills.length, 2);

    const blue_pill = pills[0];
    assert.equal(blue_pill.item.color_name, "BLUE");
    assert.equal(blue_pill.item.description, "color of the sky");

    // Update the blue pill with new data
    const updated_blue_data = {
        color_name: "DARK BLUE",
        description: "color of the deep ocean",
        type: "color",
    };

    let element_replaced = false;
    blue_pill.$element[0].replaceWith = (new_element) => {
        element_replaced = true;
        assert.equal(new_element.innerHTML, pill_html("DARK BLUE"));
    };

    widget.updatePill(blue_pill.$element[0], updated_blue_data);

    // Verify the pill element was replaced with new HTML
    assert.ok(element_replaced);
    // Verify that pill.$element was updated by updatePill
    assert.equal(blue_pill.$element.html(), pill_html("DARK BLUE"));
    // Verify the pill's internal data was updated
    assert.equal(blue_pill.item.color_name, "DARK BLUE");
    assert.equal(blue_pill.item.description, "color of the deep ocean");

    // Verify other pill is unchanged
    const red_pill = pills[1];
    assert.equal(red_pill.item.color_name, "RED");
    assert.equal(red_pill.item.description, "color of stop signs");

    // Test updating non-existent pill element - should be a no-op
    const fake_element = {};
    widget.updatePill(fake_element, updated_blue_data);
    // Blue pill data should remain unchanged
    assert.equal(blue_pill.item.color_name, "DARK BLUE");
    assert.equal(blue_pill.item.description, "color of the deep ocean");
});

function set_up_for_editing(mock_template, config_overrides = {}) {
    mock_template("input_pill.hbs", true, (data, html) => {
        $(html)[0] = `<pill-stub ${data.display_value}>`;
        $(html).length = 1;
        return html;
    });

    // The deferred blur-commit waits while the typeahead menu is hovered.
    $.set_results(".typeahead:hover", []);

    const {config, $container, $pill_input, items} = set_up();
    Object.assign(config, config_overrides);

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    const pills = widget._get_pills_for_testing();
    for (const [i, pill] of pills.entries()) {
        pill.$element.remove = noop;
        pill.$element.replaceWith = noop;
        // Pre-render the edit span (normally rendered in input_pill.hbs).
        const $edit = $.create(`pill-edit-input-${i}`);
        pill.$element.find = (sel) => (sel === ".pill-edit-input" ? $edit : {length: 0});
    }

    return {widget, pills, $container, $pill_input, items};
}

function start_editing_pill_via_dblclick($container, pill) {
    // The edit span is already inside the pill (pre-rendered in the template).
    const $edit = pill.$element.find(".pill-edit-input");

    const dblclick_handler = $container.get_on_handler("dblclick", ".pill");
    dblclick_handler.call(pill.$element[0], {
        target: {
            to_$: () => ({
                closest(_sel) {
                    return {length: 0};
                },
            }),
        },
        preventDefault: noop,
    });

    return $edit;
}

function start_editing_blue_pill(mock_template, config_overrides) {
    const info = set_up_for_editing(mock_template, config_overrides);
    const blue_pill = info.pills[0];
    const $edit = start_editing_pill_via_dblclick(info.$container, blue_pill);
    return {...info, blue_pill, $edit};
}

function press_key($edit, key) {
    $edit.get_on_handler("keydown")({key, preventDefault: noop, stopPropagation: noop});
}

function press_pill_key($container, key) {
    $container.get_on_handler(
        "keydown",
        ".pill",
    )({
        key,
        preventDefault: noop,
        stopPropagation: noop,
    });
}

function assert_pill_colors(widget, colors) {
    assert.deepEqual(
        widget.items().map((item) => item.color_name),
        colors,
    );
}

run_test("dblclick or Enter on a focused pill starts editing", ({mock_template}) => {
    const {widget, pills, $container} = set_up_for_editing(mock_template);
    const [blue_pill, red_pill] = pills;
    widget.setSetupTypeahead(() => ({shown: false, unlisten: noop}));

    const $blue_edit = start_editing_pill_via_dblclick($container, blue_pill);
    assert.ok(blue_pill.$element.hasClass("editing"));
    assert.equal($blue_edit.text(), "BLUE");

    // find(".pill:focus") is how the keydown handler locates the focused pill.
    $container.set_find_results(".pill:focus", red_pill.$element);
    press_pill_key($container, "Enter");
    const $red_edit = red_pill.$element.find(".pill-edit-input");
    assert.ok(red_pill.$element.hasClass("editing"));
    assert.equal($red_edit.text(), "RED");

    // The Enter that started the edit must not also commit it.
    for (const event_type of ["keypress", "keyup"]) {
        let stopped = false;
        $red_edit.get_on_handler(event_type).call($red_edit, {
            key: "Enter",
            preventDefault: noop,
            stopImmediatePropagation() {
                stopped = true;
            },
        });
        assert.ok(stopped);
    }
});

function test_replacing_blue_with_yellow(mock_template, replace) {
    const {widget, blue_pill, $edit, $container, items} = start_editing_blue_pill(mock_template);
    const events = [];
    widget.onPillRemove(() => {
        events.push("remove");
    });
    widget.onPillCreate(() => {
        events.push("create");
    });
    blue_pill.$element.replaceWith = () => {
        events.push("replace");
    };

    replace({widget, $edit, $container, items});

    assert.deepEqual(events, ["replace", "remove", "create"]);
    // YELLOW replaces BLUE at index 0; store.pills must stay in DOM order.
    assert.deepEqual(widget.items(), [items.yellow, items.red]);
}

run_test("Enter commits in-place edit", ({mock_template}) => {
    test_replacing_blue_with_yellow(mock_template, ({$edit, $container}) => {
        $edit.text("yellow");
        press_key($edit, "Enter");

        // Otherwise this Enter's keyup would submit the surrounding form.
        let stopped = false;
        $container.get_on_handler("keyup").call($container, {
            key: "Enter",
            stopPropagation() {
                stopped = true;
            },
        });
        assert.ok(stopped);
    });
});

run_test("typeahead selection updates pill in place", ({mock_template}) => {
    test_replacing_blue_with_yellow(mock_template, ({widget, items}) => {
        // The typeahead's updater calls updatePillAfterEdit directly.
        widget.updatePillAfterEdit(items.yellow);
    });
});

run_test("empty edit deletes the pill", ({mock_template}) => {
    const {widget, $edit} = start_editing_blue_pill(mock_template);
    let pill_removed = false;
    widget.onPillRemove(() => {
        pill_removed = true;
    });

    $edit.text("");
    press_key($edit, "Enter");

    assert_pill_colors(widget, ["RED"]);
    assert.ok(pill_removed);
});

run_test("Escape cancels in-place edit", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);

    $edit.text("yellow");
    press_key($edit, "Escape");

    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("edit box seeds and compares against the display value", ({mock_template}) => {
    // Role-based system groups display a friendly name ("Administrators")
    // that differs from their internal text ("role:administrators"). The edit
    // box must show the display value, and committing it unchanged must cancel
    // rather than validate the display string as new input.
    const display_names = {BLUE: "Blue", RED: "Red"};
    const {widget, blue_pill, $edit, $pill_input} = start_editing_blue_pill(mock_template, {
        get_display_value_from_item: (item) => display_names[item.color_name] ?? item.color_name,
    });

    assert.equal($edit.text(), "Blue");

    press_key($edit, "Enter");

    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert_pill_colors(widget, ["BLUE", "RED"]);
    assert.ok(!$pill_input.hasClass("input-validation-shake"));
    assert.ok(!blue_pill.$element.hasClass("input-validation-shake"));
});

run_test("invalid edit shakes but keeps the typed text", ({mock_template}) => {
    const {widget, blue_pill, $edit, $pill_input} = start_editing_blue_pill(mock_template);

    $edit.text("invalid_color_name");
    press_key($edit, "Enter");

    assert_pill_colors(widget, ["BLUE", "RED"]);
    // The pill shakes, not the main input.
    assert.ok(!$pill_input.hasClass("input-validation-shake"));
    assert.ok(blue_pill.$element.hasClass("input-validation-shake"));
    // The edit stays open with the text, so it can be fixed, not retyped.
    assert.ok(blue_pill.$element.hasClass("editing"));
    assert.equal($edit.text(), "invalid_color_name");
});

run_test("invalid edit reverts once focus leaves the pill", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);
    $edit.text("invalid_color_name");

    // A pill that isn't being edited has to show a valid value, so this reverts.
    $edit.get_on_handler("blur")();
    run_deferred_callbacks();

    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert.ok(blue_pill.$element.hasClass("input-validation-shake"));
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("blur ends an unchanged edit without taking focus", ({mock_template}) => {
    const {blue_pill, $edit} = start_editing_blue_pill(mock_template);

    // Pulling focus back would interrupt typing wherever the user went.
    /* istanbul ignore next */
    blue_pill.$element.trigger = () => {
        throw new Error("ending an edit on blur must not take focus");
    };

    $edit.get_on_handler("blur")();
    run_deferred_callbacks();

    assert.ok(!blue_pill.$element.hasClass("editing"));
});

run_test("deferred blur-commit bails once the edit box has focus again", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);
    $edit.text("yellow");

    // Clicking the typeahead menu blurs the edit box and then gives focus
    // back, so the edit has to survive.
    $edit.get_on_handler("blur")();
    $edit.trigger("focus");
    run_deferred_callbacks();

    assert.ok(blue_pill.$element.hasClass("editing"));
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("deferred blur-commit waits while the typeahead menu is hovered", ({mock_template}) => {
    const {widget, $edit} = start_editing_blue_pill(mock_template);
    $edit.text("yellow");

    const hovered_menus = [$.create("typeahead-menu")[0]];
    $.reset_selector(".typeahead:hover");
    $.set_results(".typeahead:hover", hovered_menus);
    $edit.get_on_handler("blur")();
    run_deferred_callbacks();
    assert_pill_colors(widget, ["BLUE", "RED"]);

    hovered_menus.pop();
    run_deferred_callbacks();
    assert_pill_colors(widget, ["YELLOW", "RED"]);
});

run_test("editing another pill resolves the in-flight edit", ({mock_template}) => {
    const {widget, blue_pill, $edit, $container, pills} = start_editing_blue_pill(mock_template);
    const red_pill = pills[1];
    $edit.text("yellow");

    // The blur-commit from that click is deferred, so it has to be resolved
    // here or the click is swallowed.
    $edit.get_on_handler("blur")();
    start_editing_pill_via_dblclick($container, red_pill);

    assert_pill_colors(widget, ["YELLOW", "RED"]);
    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert.ok(red_pill.$element.hasClass("editing"));
});

run_test("items() includes the pill being edited as its pre-edit value", ({mock_template}) => {
    const {widget} = start_editing_blue_pill(mock_template);

    // items() still reports the edited pill (as its pre-edit value) so a
    // submit read can't silently drop it; submit paths finalize first.
    assert_pill_colors(widget, ["BLUE", "RED"]);

    // getPillByPredicate, used by live-update handlers that call updatePill,
    // still skips the edited pill so a live update can't clobber the edit.
    assert.equal(
        widget.getPillByPredicate((item) => item.color_name === "BLUE"),
        undefined,
    );
    assert.ok(widget.getPillByPredicate((item) => item.color_name === "RED"));
});

run_test("finalize_pending_edit commits a valid in-flight edit", ({mock_template}) => {
    const {widget, pills, $container} = set_up_for_editing(mock_template);

    assert.ok(widget.finalize_pending_edit());
    assert_pill_colors(widget, ["BLUE", "RED"]);

    const $edit = start_editing_pill_via_dblclick($container, pills[0]);
    $edit.text("yellow");

    // A submit path calling this must see the committed value (YELLOW), not
    // the pill's pre-edit value (BLUE).
    assert.ok(widget.finalize_pending_edit());
    assert_pill_colors(widget, ["YELLOW", "RED"]);
});

run_test("finalize_pending_edit blocks an unresolved invalid edit", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);
    $edit.text("invalid_color_name");

    // The submit must be blocked rather than fall back to the pill's
    // stale, pre-edit value, and the text stays for the user to fix.
    assert.ok(!widget.finalize_pending_edit());
    assert_pill_colors(widget, ["BLUE", "RED"]);
    assert.ok(blue_pill.$element.hasClass("input-validation-shake"));
    assert.ok(blue_pill.$element.hasClass("editing"));
    assert.equal($edit.text(), "invalid_color_name");
});

run_test("ArrowRight at end of edit moves to next pill", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);

    let next_pill_focused = false;
    const $next_pill = $.create("next-pill");
    $next_pill.trigger = () => {
        next_pill_focused = true;
    };
    blue_pill.$element.next = () => $next_pill;

    press_key($edit, "ArrowRight");

    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert.ok(next_pill_focused);
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("ArrowLeft at start of edit cancels and restores pill", ({mock_template}) => {
    const {widget, blue_pill, $edit} = start_editing_blue_pill(mock_template);

    let prev_pill_focused = false;
    const $prev_pill = $.create("prev-pill");
    $prev_pill.trigger = () => {
        prev_pill_focused = true;
    };
    blue_pill.$element.prev = (sel) => (sel === ".pill" ? $prev_pill : {length: 0});

    press_key($edit, "ArrowLeft");

    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert.ok(prev_pill_focused);
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("Enter leaves an open typeahead to handle itself", ({mock_template}) => {
    const {widget, pills, $container} = set_up_for_editing(mock_template);
    const blue_pill = pills[0];

    // We ask this edit's own typeahead whether its menu is open, since the
    // search typeahead leaves a highlighted row in the DOM even when hidden.
    const typeahead_stub = {
        shown: true,
        unlisten: noop,
    };
    widget.setSetupTypeahead(() => typeahead_stub);

    const $edit = start_editing_pill_via_dblclick($container, blue_pill);
    $edit.text("yellow");
    press_key($edit, "Enter");

    // The typeahead's keyup handler applies the suggestion, so the edit is
    // still in flight.
    assert.ok(blue_pill.$element.hasClass("editing"));
    assert_pill_colors(widget, ["BLUE", "RED"]);

    typeahead_stub.shown = false;
    press_key($edit, "Enter");
    assert_pill_colors(widget, ["YELLOW", "RED"]);
});

run_test("disable_pill_editing keeps pills read-only", ({mock_template}) => {
    const {widget, blue_pill, $container} = start_editing_blue_pill(mock_template, {
        disable_pill_editing: true,
    });
    assert.ok(!blue_pill.$element.hasClass("editing"));

    // Enter on a focused pill must not start an edit either.
    $container.set_find_results(".pill:focus", blue_pill.$element);
    press_pill_key($container, "Enter");
    assert.ok(!blue_pill.$element.hasClass("editing"));
    assert_pill_colors(widget, ["BLUE", "RED"]);
});

run_test("editing a pill again tears down the previous edit", ({mock_template}) => {
    const {widget, pills, $container} = set_up_for_editing(mock_template);
    const blue_pill = pills[0];

    // Every edit sets up its own typeahead, so every edit has to tear it down.
    let typeaheads_set_up = 0;
    let typeaheads_torn_down = 0;
    widget.setSetupTypeahead(() => {
        typeaheads_set_up += 1;
        return {
            shown: false,
            unlisten() {
                typeaheads_torn_down += 1;
            },
        };
    });

    const $edit = start_editing_pill_via_dblclick($container, blue_pill);
    assert.equal(typeaheads_set_up, 1);
    assert.equal(typeaheads_torn_down, 0);

    press_key($edit, "Escape");
    assert.equal(typeaheads_torn_down, 1);

    // Editing it again reuses the same element, so nothing from the previous
    // edit may still be attached: zjquery throws on a duplicate handler.
    assert.equal(start_editing_pill_via_dblclick($container, blue_pill), $edit);
    assert.equal(typeaheads_set_up, 2);
    assert.equal(typeaheads_torn_down, 1);

    // Committing replaces the pill element, but the typeahead is still ours.
    $edit.text("yellow");
    press_key($edit, "Enter");
    assert_pill_colors(widget, ["YELLOW", "RED"]);
    assert.equal(typeaheads_torn_down, 2);
});
