"use strict";

const rm = zrequire("rendered_markdown");
const people = zrequire("people");
zrequire("user_groups");
zrequire("stream_data");
zrequire("timerender");
set_global("$", global.make_zjquery());

set_global("rtl", {
    get_direction: () => "ltr",
});

const iago = {
    email: "iago@zulip.com",
    user_id: 30,
    full_name: "Iago",
};

const cordelia = {
    email: "cordelia@zulup.com",
    user_id: 31,
    full_name: "Cordelia",
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
        array.forEach((e) => {
            func.call(e);
        });
    };
    return {each};
};

set_global("page_params", {emojiset: "apple"});

const get_content_element = () => {
    $.clear_all_elements();
    const $content = $.create(".rendered_markdown");
    $content.set_find_results(".user-mention", $array([]));
    $content.set_find_results(".user-group-mention", $array([]));
    $content.set_find_results("a.stream", $array([]));
    $content.set_find_results("a.stream-topic", $array([]));
    $content.set_find_results("time", $array([]));
    $content.set_find_results("span.timestamp-error", $array([]));
    $content.set_find_results(".emoji", $array([]));
    $content.set_find_results("div.spoiler-header", $array([]));
    $content.set_find_results("div.codehilite", $array([]));
    return $content;
};

run_test("misc_helpers", () => {
    const elem = $.create(".user-mention");
    rm.set_name_in_mention_element(elem, "Aaron");
    assert.equal(elem.text(), "@Aaron");
    elem.addClass("silent");
    rm.set_name_in_mention_element(elem, "Aaron, but silent");
    assert.equal(elem.text(), "Aaron, but silent");
});

run_test("user-mention", () => {
    // Setup
    const $content = get_content_element();
    const $iago = $.create(".user-mention(iago)");
    $iago.set_find_results(".highlight", false);
    $iago.attr("data-user-id", iago.user_id);
    const $cordelia = $.create(".user-mention(cordelia)");
    $cordelia.set_find_results(".highlight", false);
    $cordelia.attr("data-user-id", cordelia.user_id);
    $content.set_find_results(".user-mention", $array([$iago, $cordelia]));

    // Initial asserts
    assert(!$iago.hasClass("user-mention-me"));
    assert.equal($iago.text(), "never-been-set");
    assert.equal($cordelia.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert($iago.hasClass("user-mention-me"));
    assert.equal($iago.text(), `@${iago.full_name}`);
    assert.equal($cordelia.text(), `@${cordelia.full_name}`);
});

run_test("user-group-mention", () => {
    // Setup
    const $content = get_content_element();
    const $group_me = $.create(".user-group-mention(me)");
    $group_me.set_find_results(".highlight", false);
    $group_me.attr("data-user-group-id", group_me.id);
    const $group_other = $.create(".user-group-mention(other)");
    $group_other.set_find_results(".highlight", false);
    $group_other.attr("data-user-group-id", group_other.id);
    $content.set_find_results(".user-group-mention", $array([$group_me, $group_other]));

    // Initial asserts
    assert(!$group_me.hasClass("user-mention-me"));
    assert.equal($group_me.text(), "never-been-set");
    assert.equal($group_other.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert($group_me.hasClass("user-mention-me"));
    assert.equal($group_me.text(), `@${group_me.name}`);
    assert.equal($group_other.text(), `@${group_other.name}`);
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
    $stream_topic.text("#random>topic name");
    $content.set_find_results("a.stream", $array([$stream]));
    $content.set_find_results("a.stream-topic", $array([$stream_topic]));

    // Initial asserts
    assert.equal($stream.text(), "never-been-set");
    assert.equal($stream_topic.text(), "#random>topic name");

    rm.update_elements($content);

    // Final asserts
    assert.equal($stream.text(), `#${stream.name}`);
    assert.equal($stream_topic.text(), `#${stream.name} > topic name`);
});

run_test("timestamp", () => {
    // Setup
    const $content = get_content_element();
    const $timestamp = $.create("timestamp(valid)");
    $timestamp.attr("datetime", "1970-01-01T00:00:01Z");
    const $timestamp_invalid = $.create("timestamp(invalid)");
    $timestamp_invalid.attr("datetime", "invalid");
    $content.set_find_results("time", $array([$timestamp, $timestamp_invalid]));
    blueslip.expect("error", "Moment could not parse datetime supplied by backend: invalid");

    // Initial asserts
    assert.equal($timestamp.text(), "never-been-set");
    assert.equal($timestamp_invalid.text(), "never-been-set");

    rm.update_elements($content);

    // Final asserts
    assert.equal($timestamp.text(), "Thu, Jan 1 1970, 12:00 AM");
    assert.equal(
        $timestamp.attr("title"),
        "This time is in your timezone. Original text was 'never-been-set'.",
    );
    assert.equal($timestamp_invalid.text(), "never-been-set");
});

run_test("timestamp-twenty-four-hour-time", () => {
    const $content = get_content_element();
    const $timestamp = $.create("timestamp");
    $timestamp.attr("datetime", "2020-07-15T20:40:00Z");
    $content.set_find_results("time", $array([$timestamp]));

    // We will temporarily change the 24h setting for this test.
    const old_page_params = global.page_params;

    set_global("page_params", {...old_page_params, twenty_four_hour_time: true});
    rm.update_elements($content);
    assert.equal($timestamp.text(), "Wed, Jul 15 2020, 20:40");

    set_global("page_params", {...old_page_params, twenty_four_hour_time: false});
    rm.update_elements($content);
    assert.equal($timestamp.text(), "Wed, Jul 15 2020, 8:40 PM");

    // Set page_params back to its original value.
    set_global("page_params", old_page_params);
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
    const $emoji = $.create(".emoji");
    $emoji.attr("title", "tada");
    let called = false;
    $emoji.replaceWith = (f) => {
        const text = f.call($emoji);
        assert.equal(":tada:", text);
        called = true;
    };
    $content.set_find_results(".emoji", $emoji);
    page_params.emojiset = "text";

    rm.update_elements($content);

    assert(called);

    // Set page parameters back so that test run order is independent
    page_params.emojiset = "apple";
});

run_test("spoiler-header", () => {
    // Setup
    const $content = get_content_element();
    const $header = $.create("div.spoiler-header");
    $content.set_find_results("div.spoiler-header", $array([$header]));

    // Test that the show/hide button gets added to a spoiler header.
    const label = "My Spoiler Header";
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
    $header.html("");
    rm.update_elements($content);
    assert.equal(toggle_button_html + "<p>translated: Spoiler</p>", $header.html());
});
