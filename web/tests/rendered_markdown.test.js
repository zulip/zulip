"use strict";

const {strict: assert} = require("assert");

const {mock_cjs, mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {user_settings} = require("./lib/zpage_params");

let clipboard_args;
class Clipboard {
    constructor(...args) {
        clipboard_args = args;
    }
    on(_success, show_copied_confirmation) {
        show_copied_confirmation();
    }
}

mock_cjs("clipboard", Clipboard);

const realm_playground = mock_esm("../src/realm_playground");
const tippyjs = mock_esm("../src/tippyjs");
user_settings.emojiset = "apple";

const rm = zrequire("rendered_markdown");
const people = zrequire("people");
const user_groups = zrequire("user_groups");
const stream_data = zrequire("stream_data");

const iago = {
    email: "iago@zulip.com",
    user_id: 30,
    full_name: "Iago",
};

const cordelia = {
    email: "cordelia@zulip.com",
    user_id: 31,
    full_name: "Cordelia Lear",
};
people.init();
people.add_active_user(iago);
people.add_active_user(cordelia);
people.initialize_current_user(iago.user_id);

const group_me = {
    name: "my user group",
    id: 1,
    members: [iago.user_id, cordelia.user_id],
};
const group_other = {
    name: "other user group",
    id: 2,
    members: [cordelia.user_id],
};
user_groups.initialize({
    realm_user_groups: [group_me, group_other],
});

const stream = {
    subscribed: true,
    color: "yellow",
    name: "test",
    stream_id: 3,
    is_muted: true,
    invite_only: false,
};
stream_data.add_sub(stream);

const $array = (array) => {
    const each = (func) => {
        for (const e of array) {
            func.call(e);
        }
    };
    return {each};
};

function set_closest_dot_find_result($content, value) {
    $content.closest = (closest_opts) => {
        assert.equal(closest_opts, ".recipient_row");
        const find = (find_opts) => {
            assert.equal(find_opts, ".message_header.message_header_stream");
            return value;
        };
        return {find};
    };
}

const get_content_element = () => {
    const $content = $.create("content-stub");
    $content.set_find_results(".user-mention", $array([]));
    $content.set_find_results(".user-group-mention", $array([]));
    $content.set_find_results("a.stream", $array([]));
    $content.set_find_results("a.stream-topic", $array([]));
    $content.set_find_results("time", $array([]));
    $content.set_find_results("span.timestamp-error", $array([]));
    $content.set_find_results(".emoji", $array([]));
    $content.set_find_results("div.spoiler-header", $array([]));
    $content.set_find_results("div.codehilite", $array([]));
    set_closest_dot_find_result($content, []);

    // Fend off dumb security bugs by forcing devs to be
    // intentional about HTML manipulation.
    /* istanbul ignore next */
    function security_violation() {
        throw new Error(`
            Be super careful about HTML manipulation.

            Make sure your test objects set up their own
            functions to validate that calls to html/prepend/append
            use trusted values.
        `);
    }
    $content.html = security_violation;
    $content.prepend = security_violation;
    $content.append = security_violation;
    return $content;
};

run_test("misc_helpers", () => {
    const $elem = $.create("user-mention");
    rm.set_name_in_mention_element($elem, "Aaron");
    assert.equal($elem.text(), "@Aaron");
    $elem.addClass("silent");
    rm.set_name_in_mention_element($elem, "Aaron, but silent");
    assert.equal($elem.text(), "Aaron, but silent");
});

run_test("user-mention", () => {
    // Setup
    const $content = get_content_element();
    const $iago = $.create("user-mention(iago)");
    $iago.set_find_results(".highlight", false);
    $iago.attr("data-user-id", iago.user_id);
    const $cordelia = $.create("user-mention(cordelia)");
    $cordelia.set_find_results(".highlight", false);
    $cordelia.attr("data-user-id", cordelia.user_id);
    $content.set_find_results(".user-mention", $array([$iago, $cordelia]));

    // Initial asserts
    assert.ok(!$iago.hasClass("user-mention-me"));
    assert.equal($iago.text(), "never-been-set");
    assert.equal($cordelia.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert.ok($iago.hasClass("user-mention-me"));
    assert.equal($iago.text(), `@${iago.full_name}`);
    assert.equal($cordelia.text(), `@${cordelia.full_name}`);
});

run_test("user-mention PM (wildcard)", () => {
    // Setup
    const $content = get_content_element();
    const $mention = $.create("mention");
    $mention.attr("data-user-id", "*");
    $content.set_find_results(".user-mention", $array([$mention]));

    assert.ok(!$mention.hasClass("user-mention-me"));
    rm.update_elements($content);
    assert.ok($mention.hasClass("user-mention-me"));
});

run_test("user-mention Stream subbed (wildcard)", ({override_rewire}) => {
    // Setup
    const $content = get_content_element();
    const $mention = $.create("mention");
    $mention.attr("data-user-id", "*");
    $content.set_find_results(".user-mention", $array([$mention]));
    const attr = () => stream.stream_id;
    set_closest_dot_find_result($content, {attr, length: 1});
    override_rewire(stream_data, "is_user_subscribed", () => true);

    assert.ok(!$mention.hasClass("user-mention-me"));
    rm.update_elements($content);
    assert.ok($mention.hasClass("user-mention-me"));
});

run_test("user-mention Stream not subbed (wildcard)", ({override_rewire}) => {
    // Setup
    const $content = get_content_element();
    const $mention = $.create("mention");
    $mention.attr("data-user-id", "*");
    $content.set_find_results(".user-mention", $array([$mention]));
    const attr = () => 1;
    set_closest_dot_find_result($content, {attr, length: 1});
    override_rewire(stream_data, "is_user_subscribed", () => false);

    // Don't add user-mention-me class.
    assert.ok(!$mention.hasClass("user-mention-me"));
    rm.update_elements($content);
    assert.ok(!$mention.hasClass("user-mention-me"));
});

run_test("user-mention (email)", () => {
    // Setup
    const $content = get_content_element();
    const $mention = $.create("mention");
    $mention.attr("data-user-email", cordelia.email);
    $mention.set_find_results(".highlight", false);
    $content.set_find_results(".user-mention", $array([$mention]));

    rm.update_elements($content);
    assert.ok(!$mention.hasClass("user-mention-me"));
    assert.equal($mention.text(), "@Cordelia Lear");
});

run_test("user-mention (missing)", () => {
    const $content = get_content_element();
    const $mention = $.create("mention");
    $content.set_find_results(".user-mention", $array([$mention]));

    rm.update_elements($content);
    assert.ok(!$mention.hasClass("user-mention-me"));
});

run_test("user-group-mention", () => {
    // Setup
    const $content = get_content_element();
    const $group_me = $.create("user-group-mention(me)");
    $group_me.set_find_results(".highlight", false);
    $group_me.attr("data-user-group-id", group_me.id);
    const $group_other = $.create("user-group-mention(other)");
    $group_other.set_find_results(".highlight", false);
    $group_other.attr("data-user-group-id", group_other.id);
    $content.set_find_results(".user-group-mention", $array([$group_me, $group_other]));

    // Initial asserts
    assert.ok(!$group_me.hasClass("user-mention-me"));
    assert.equal($group_me.text(), "never-been-set");
    assert.equal($group_other.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert.ok($group_me.hasClass("user-mention-me"));
    assert.equal($group_me.text(), `@${group_me.name}`);
    assert.equal($group_other.text(), `@${group_other.name}`);
});

run_test("user-group-mention (error)", () => {
    const $content = get_content_element();
    const $group = $.create("user-group-mention(bogus)");
    $group.attr("data-user-group-id", "not-even-a-number");
    $content.set_find_results(".user-group-mention", $array([$group]));

    rm.update_elements($content);

    assert.ok(!$group.hasClass("user-mention-me"));
});

run_test("user-group-mention (missing)", () => {
    const $content = get_content_element();
    const $group = $.create("whatever");
    $content.set_find_results(".user-group-mention", $array([$group]));

    rm.update_elements($content);

    assert.ok(!$group.hasClass("user-mention-me"));
});

run_test("stream-links", () => {
    // Setup
    const $content = get_content_element();
    const $stream = $.create("a.stream");
    $stream.set_find_results(".highlight", false);
    $stream.attr("data-stream-id", stream.stream_id);
    const $stream_topic = $.create("a.stream-topic");
    $stream_topic.set_find_results(".highlight", false);
    $stream_topic.attr("data-stream-id", stream.stream_id);
    $stream_topic.text("#random > topic name > still the topic name");
    $content.set_find_results("a.stream", $array([$stream]));
    $content.set_find_results("a.stream-topic", $array([$stream_topic]));

    // Initial asserts
    assert.equal($stream.text(), "never-been-set");
    assert.equal($stream_topic.text(), "#random > topic name > still the topic name");

    rm.update_elements($content);

    // Final asserts
    assert.equal($stream.text(), `#${stream.name}`);
    assert.equal($stream_topic.text(), `#${stream.name} > topic name > still the topic name`);
});

run_test("timestamp without time", () => {
    const $content = get_content_element();
    const $timestamp = $.create("timestamp without actual time");
    $content.set_find_results("time", $array([$timestamp]));

    rm.update_elements($content);
    assert.equal($timestamp.text(), "never-been-set");
});

run_test("timestamp", ({mock_template}) => {
    mock_template("markdown_timestamp.hbs", true, (data, html) => {
        assert.deepEqual(data, {text: "Thu, Jan 1, 1970, 12:00 AM"});
        return html;
    });

    // Setup
    const $content = get_content_element();
    const $timestamp = $.create("timestamp(valid)");
    $timestamp.attr("datetime", "1970-01-01T00:00:01Z");
    const $timestamp_invalid = $.create("timestamp(invalid)");
    $timestamp_invalid.attr("datetime", "invalid");
    $content.set_find_results("time", $array([$timestamp, $timestamp_invalid]));
    blueslip.expect("error", "Could not parse datetime supplied by backend");

    // Initial asserts
    assert.equal($timestamp.text(), "never-been-set");
    assert.equal($timestamp_invalid.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert.equal($timestamp.html(), '<i class="fa fa-clock-o"></i>\nThu, Jan 1, 1970, 12:00 AM\n');
    assert.equal($timestamp_invalid.text(), "never-been-set");
});

run_test("timestamp-twenty-four-hour-time", ({mock_template, override}) => {
    mock_template("markdown_timestamp.hbs", true, (data, html) => {
        // sanity check incoming data
        assert.ok(data.text.startsWith("Wed, Jul 15, 2020, "));
        return html;
    });

    const $content = get_content_element();
    const $timestamp = $.create("timestamp");
    $timestamp.attr("datetime", "2020-07-15T20:40:00Z");
    $content.set_find_results("time", $array([$timestamp]));

    // We will temporarily change the 24h setting for this test.
    override(user_settings, "twenty_four_hour_time", true);
    rm.update_elements($content);
    assert.equal($timestamp.html(), '<i class="fa fa-clock-o"></i>\nWed, Jul 15, 2020, 20:40\n');

    override(user_settings, "twenty_four_hour_time", false);
    rm.update_elements($content);
    assert.equal($timestamp.html(), '<i class="fa fa-clock-o"></i>\nWed, Jul 15, 2020, 8:40 PM\n');
});

run_test("timestamp-error", () => {
    // Setup
    const $content = get_content_element();
    const $timestamp_error = $.create("timestamp-error");
    $timestamp_error.text("Invalid time format: the-time-format");
    $content.set_find_results("span.timestamp-error", $array([$timestamp_error]));

    // Initial assert
    assert.equal($timestamp_error.text(), "Invalid time format: the-time-format");

    rm.update_elements($content);

    // Final assert
    assert.equal($timestamp_error.text(), "translated: Invalid time format: the-time-format");
});

run_test("emoji", () => {
    // Setup
    const $content = get_content_element();
    const $emoji = $.create("emoji-stub");
    $emoji.attr("title", "tada");
    let called = false;
    $emoji.replaceWith = (f) => {
        const text = f.call($emoji);
        assert.equal(":tada:", text);
        called = true;
    };
    $content.set_find_results(".emoji", $emoji);
    user_settings.emojiset = "text";

    rm.update_elements($content);

    assert.ok(called);

    // Set page parameters back so that test run order is independent
    user_settings.emojiset = "apple";
});

run_test("spoiler-header", () => {
    // Setup
    const $content = get_content_element();
    const $header = $.create("div.spoiler-header");
    $content.set_find_results("div.spoiler-header", $array([$header]));

    // Test that the show/hide button gets added to a spoiler header.
    const label = "My spoiler header";
    const toggle_button_html =
        '<span class="spoiler-button" aria-expanded="false"><span class="spoiler-arrow"></span></span>';
    $header.html(label);
    rm.update_elements($content);
    assert.equal(toggle_button_html + label, $header.html());
});

run_test("spoiler-header-empty-fill", () => {
    // Setup
    const $content = get_content_element();
    const $header = $.create("div.spoiler-header");
    $content.set_find_results("div.spoiler-header", $array([$header]));

    // Test that an empty header gets the default text applied (through i18n filter).
    const toggle_button_html =
        '<span class="spoiler-button" aria-expanded="false"><span class="spoiler-arrow"></span></span>';
    $header.empty();
    rm.update_elements($content);
    assert.equal(toggle_button_html + "<p>translated HTML: Spoiler</p>", $header.html());
});

function assert_clipboard_setup() {
    assert.equal(clipboard_args[0], "copy-code-stub");
    const text = clipboard_args[1].text({
        to_$: () => ({
            siblings(arg) {
                assert.equal(arg, "code");
                return {
                    text: () => "text",
                };
            },
        }),
    });
    assert.equal(text, "text");
}

function test_code_playground(mock_template, viewing_code) {
    const $content = get_content_element();
    const $hilite = $.create("div.codehilite");
    const $pre = $.create("hilite-pre");
    $content.set_find_results("div.codehilite", $array([$hilite]));
    $hilite.set_find_results("pre", $pre);

    $hilite.data("code-language", "javascript");

    const $copy_code_button = $.create("copy_code_button", {children: ["copy-code-stub"]});
    const $view_code_in_playground = $.create("view_code_in_playground");

    // The code playground code prepends a few buttons
    // to the <pre> section of a highlighted piece of code.
    // The args to prepend should be jQuery objects (or in
    // our case "fake" zjquery objects).
    const prepends = [];
    $pre.prepend = (arg) => {
        assert.ok(arg.__zjquery, "We should only prepend jQuery objects.");
        prepends.push(arg);
    };

    mock_template("copy_code_button.hbs", false, (data) => {
        assert.equal(data, undefined);
        return {to_$: () => $copy_code_button};
    });

    if (viewing_code) {
        mock_template("view_code_in_playground.hbs", false, (data) => {
            assert.equal(data, undefined);
            return {to_$: () => $view_code_in_playground};
        });
    }

    rm.update_elements($content);

    return {
        prepends,
        $copy_code: $copy_code_button,
        $view_code: $view_code_in_playground,
    };
}

run_test("code playground none", ({override, mock_template}) => {
    override(realm_playground, "get_playground_info_for_languages", (language) => {
        assert.equal(language, "javascript");
        return undefined;
    });

    override(tippyjs, "show_copied_confirmation", () => {});

    const {prepends, $copy_code, $view_code} = test_code_playground(mock_template, false);
    assert.deepEqual(prepends, [$copy_code]);
    assert_clipboard_setup();

    assert.equal($view_code.attr("data-tippy-content"), undefined);
    assert.equal($view_code.attr("aria-label"), undefined);
});

run_test("code playground single", ({override, mock_template}) => {
    override(realm_playground, "get_playground_info_for_languages", (language) => {
        assert.equal(language, "javascript");
        return [{name: "Some Javascript Playground"}];
    });

    override(tippyjs, "show_copied_confirmation", () => {});

    const {prepends, $copy_code, $view_code} = test_code_playground(mock_template, true);
    assert.deepEqual(prepends, [$view_code, $copy_code]);
    assert_clipboard_setup();

    assert.equal(
        $view_code.attr("data-tippy-content"),
        "translated: View in Some Javascript Playground",
    );
    assert.equal($view_code.attr("aria-label"), "translated: View in Some Javascript Playground");
    assert.equal($view_code.attr("aria-haspopup"), undefined);
});

run_test("code playground multiple", ({override, mock_template}) => {
    override(realm_playground, "get_playground_info_for_languages", (language) => {
        assert.equal(language, "javascript");
        return ["whatever", "whatever"];
    });

    override(tippyjs, "show_copied_confirmation", () => {});

    const {prepends, $copy_code, $view_code} = test_code_playground(mock_template, true);
    assert.deepEqual(prepends, [$view_code, $copy_code]);
    assert_clipboard_setup();

    assert.equal($view_code.attr("data-tippy-content"), "translated: View in playground");
    assert.equal($view_code.attr("aria-label"), "translated: View in playground");
    assert.equal($view_code.attr("aria-haspopup"), "true");
});

run_test("rtl", () => {
    const $content = get_content_element();

    $content.text("مرحبا");

    assert.ok(!$content.hasClass("rtl"));
    rm.update_elements($content);
    assert.ok($content.hasClass("rtl"));
});
