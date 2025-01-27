"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

set_global("document", {});
class ClipboardEvent {}
set_global("ClipboardEvent", ClipboardEvent);

mock_esm("../src/ui_util", {
    place_caret_at_end: noop,
});

set_global("getSelection", () => ({
    anchorOffset: 0,
}));

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

    $pill_input.before = ($elem) => {
        inserted_before = true;
        assert.equal($elem.html(), expected_html);
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

    $pill_input[0] = {};
    $pill_input.length = 1;
    $pill_input.before = noop;

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
        $(html)[0] = `<pill-stub ${data.display_value}>`;
        $(html).length = 1;
        return html;
    });

    const info = set_up();
    const config = info.config;
    const $container = info.$container;

    const widget = input_pill.create(config);
    widget.appendValue("blue,red");

    const copy_handler = $container.get_on_handler("copy", ".pill");

    let copied_text;

    const $pill_stub = "<pill-stub RED>";

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

    copy_handler.call($pill_stub, e);

    assert.equal(copied_text, "RED");
});

run_test("paste to input", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (_data, html) => html);

    const info = set_up();
    const config = info.config;
    const $container = info.$container;
    const items = info.items;

    const widget = input_pill.create(config);

    const paste_handler = $container.get_on_handler("paste", ".input");

    const paste_text = "blue,yellow";

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

    let entered = false;
    widget.createPillonPaste(() => {
        entered = true;
    });

    paste_handler(e);
    assert.ok(entered);
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

    let prev_focused = false;
    let next_focused = false;

    const $pill_stub = {
        prev: () => ({
            trigger(type) {
                if (type === "focus") {
                    prev_focused = true;
                }
            },
        }),
        next: () => ({
            trigger(type) {
                if (type === "focus") {
                    next_focused = true;
                }
            },
        }),
    };

    $container.set_find_results(".pill:focus", $pill_stub);

    // We use the same stub to test both arrows, since we don't
    // actually cause any real state changes here.  We stub out
    // the only interaction, which is to move the focus.
    test_key("ArrowLeft");
    assert.ok(prev_focused);

    test_key("ArrowRight");
    assert.ok(next_focused);
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

    let last_pill_focused = false;

    $container.set_find_results(".pill", {
        last: () => ({
            trigger(type) {
                if (type === "focus") {
                    last_pill_focused = true;
                }
            },
        }),
    });

    key_handler({
        key: "ArrowLeft",
    });

    assert.ok(last_pill_focused);
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
        $(html).length = 1;
        $(html)[0] = `<pill-stub ${data.display_value}>`;
        return html;
    });

    const info = set_up();

    const config = info.config;
    const $pill_input = info.$pill_input;
    const items = info.items;
    const $container = info.$container;

    const inserted_html = [];
    $pill_input.before = ($elem) => {
        inserted_html.push($elem.html());
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
        return (event) => {
            assert.equal(event, "focus");
            color_focused = color;
        };
    }

    const pills = widget._get_pills_for_testing();
    for (const pill of pills) {
        pill.$element.remove = set_colored_removed_func(pill.item.color_name);
        pill.$element.trigger = handle_event(pill.item.color_name);
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

    let prev_pill_focused = false;
    const $prev_pill_stub = $("<prev-stub>");
    $prev_pill_stub.trigger = (type) => {
        if (type === "focus") {
            prev_pill_focused = true;
        }
    };
    yellow_pill.$element.prev = () => $prev_pill_stub;
    yellow_pill.$element.next = () => $("<next-stub>");

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
    assert.ok(prev_pill_focused);
    color_removed = undefined;

    prev_pill_focused = false;
    assert.deepEqual(widget.items(), [items.blue, items.red]);

    const $focus_pill_stub = {
        prev: () => $prev_pill_stub,
        next: () => $("<next-stub>"),
        [0]: "<pill-stub RED>",
        length: 1,
    };

    $container.set_find_results(".pill:focus", $focus_pill_stub);

    const red_pill = pills.find((pill) => pill.item.color_name === "RED");
    // Disabled pill should not be removed.
    red_pill.disabled = true;

    key_handler = $container.get_on_handler("keydown", ".pill");
    key_handler({
        key: "Backspace",
        preventDefault: noop,
    });

    assert.equal(color_removed, undefined);
    assert.ok(prev_pill_focused);

    // We should be able to remove the pill after marking it as not
    // disabled.
    red_pill.disabled = false;
    prev_pill_focused = false;
    assert.deepEqual(widget.items(), [items.blue, items.red]);

    key_handler({
        key: "Backspace",
        preventDefault: noop,
    });
    assert.equal(color_removed, "RED");
    assert.ok(prev_pill_focused);
});

run_test("exit button on pill", ({mock_template}) => {
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        assert.ok(html.startsWith, "<div class='pill'");
        $(html)[0] = `<pill-stub ${data.display_value}>`;
        $(html).length = 1;
        return html;
    });
    $(".narrow_to_compose_recipients").toggleClass = noop;

    const info = set_up();

    const config = info.config;
    const items = info.items;
    const $container = info.$container;

    const widget = input_pill.create(config);

    widget.appendValue("blue,red");

    const pills = widget._get_pills_for_testing();
    for (const pill of pills) {
        pill.$element.remove = noop;
    }

    const $curr_pill_stub = {
        [0]: "<pill-stub BLUE>",
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
    const animation_end_handler = $container.get_on_handler("animationend", ".input");

    let shake_class_removed = false;

    const input_stub = {
        to_$: () => ({
            removeClass(cls) {
                assert.equal(cls, "shake");
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
    $stub.is = (sel) => {
        assert.equal(sel, ".pill-container");
        return true;
    };

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

    $pill_input.before = noop;
    $pill_input[0] = {};
    $pill_input.length = 1;

    const widget = input_pill.create(config);

    // First test some early-exit code.
    widget.appendValue("");
    assert.deepEqual(widget._get_pills_for_testing(), []);

    // Now set up real data.
    widget.appendValue("red,yellow,blue");

    const pills = widget._get_pills_for_testing();

    const removed_colors = [];
    for (const pill of pills) {
        pill.$element.remove = () => {
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
