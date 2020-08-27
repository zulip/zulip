"use strict";

const assert = require("assert").strict;

const common = require("../puppeteer_lib/common");

async function get_stream_li(page, stream_name) {
    const stream_id = await common.get_stream_id(page, stream_name);
    return `#stream_filters [data-stream-id="${stream_id}"]`;
}

async function expect_home(page) {
    await common.check_messages_sent(page, "zhome", [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Verona > other topic", ["verona other topic c"]],
        ["Denmark > test", ["denmark message"]],
        ["You and Cordelia Lear, King Hamlet", ["group pm a", "group pm b"]],
        ["You and Cordelia Lear", ["pm c"]],
        ["Verona > test", ["verona test d"]],
        ["You and Cordelia Lear, King Hamlet", ["group pm d"]],
        ["You and Cordelia Lear", ["pm e"]],
    ]);
}

async function expect_verona_stream(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Verona > other topic", ["verona other topic c"]],
        ["Verona > test", ["verona test d"]],
    ]);
    assert.strictEqual(await page.title(), "Verona - Zulip Dev - Zulip");
}

async function expect_verona_stream_test_topic(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["Verona > test", ["verona test a", "verona test b", "verona test d"]],
    ]);
    assert.strictEqual(
        await common.get_text_from_selector(page, "#left_bar_compose_stream_button_big"),
        "New topic",
    );
}

async function expect_verona_other_topic(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["Verona > other topic", ["verona other topic c"]],
    ]);
}

async function expect_test_topic(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Denmark > test", ["denmark message"]],
        ["Verona > test", ["verona test d"]],
    ]);
}

async function expect_huddle(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["You and Cordelia Lear, King Hamlet", ["group pm a", "group pm b", "group pm d"]],
    ]);
    assert.strictEqual(await page.title(), "Cordelia Lear, King Hamlet - Zulip Dev - Zulip");
}

async function expect_cordelia_private_narrow(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [["You and Cordelia Lear", ["pm c", "pm e"]]]);
}

async function un_narrow(page) {
    if (await page.evaluate(() => $(".message_comp").is(":visible"))) {
        await page.keyboard.press("Escape");
    }
    await page.keyboard.press("Escape");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    assert.strictEqual(await page.title(), "home - Zulip Dev - Zulip");
}

async function un_narrow_by_clicking_org_icon(page) {
    await page.click(".brand");
}

async function test_navigations_from_home(page) {
    console.log("Narrowing by clicking stream");
    await page.evaluate(() => $(`*[title='Narrow to stream "Verona"']`).click());
    await expect_verona_stream(page);

    assert.strictEqual(await page.title(), "Verona - Zulip Dev - Zulip");
    await un_narrow(page);
    await expect_home(page);

    console.log("Narrowing by clicking topic");
    await page.click('*[title="Narrow to stream \\"Verona\\", topic \\"test\\""]');
    await expect_verona_stream_test_topic(page);

    await un_narrow_by_clicking_org_icon(page);
    await expect_home(page);

    console.log("Narrowing by clicking group personal header");
    await page.evaluate(() =>
        $('*[title="Narrow to your private messages with Cordelia Lear, King Hamlet"]').click(),
    );
    await expect_huddle(page);

    await un_narrow_by_clicking_org_icon(page);
    await expect_home(page);
}

async function search_and_check(page, search_str, item_to_select, check, expected_narrow_title) {
    await common.select_item_via_typeahead(page, "#search_query", search_str, item_to_select);
    await check(page);
    assert.strictEqual(await page.title(), expected_narrow_title);
    await un_narrow(page);
    await expect_home(page);
}

async function search_silent_user(page, str, item) {
    await common.select_item_via_typeahead(page, "#search_query", str, item);
    await page.waitForSelector("#silent_user", {visible: true});
    const expect_message = "You haven't received any messages sent by this user yet!";
    assert.strictEqual(await common.get_text_from_selector(page, "#silent_user"), expect_message);
    await un_narrow(page);
}

async function expect_non_existing_user(page) {
    await page.waitForSelector("#non_existing_user", {visible: true});
    const expected_message = "This user does not exist!";
    assert.strictEqual(
        await common.get_text_from_selector(page, "#non_existing_user"),
        expected_message,
    );
}

async function expect_non_existing_users(page) {
    await page.waitForSelector("#non_existing_users", {visible: true});
    const expected_message = "One or more of these users do not exist!";
    assert.strictEqual(
        await common.get_text_from_selector(page, "#non_existing_users"),
        expected_message,
    );
}

async function search_non_existing_user(page, str, item) {
    await common.select_item_via_typeahead(page, "#search_query", str, item);
    await expect_non_existing_user(page);
    await un_narrow(page);
}

async function search_tests(page) {
    await search_and_check(
        page,
        "Verona",
        "Stream",
        expect_verona_stream,
        "Verona - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "Cordelia",
        "Private",
        expect_cordelia_private_narrow,
        "Cordelia Lear - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona",
        "",
        expect_verona_stream,
        "Verona - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona topic:test",
        "",
        expect_verona_stream_test_topic,
        "test - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona topic:other+topic",
        "",
        expect_verona_other_topic,
        "other topic - Zulip Dev - Zulip",
    );

    await search_and_check(page, "topic:test", "", expect_test_topic, "home - Zulip Dev - Zulip");

    await search_silent_user(page, "sender:emailgateway@zulip.com", "");

    await search_non_existing_user(page, "sender:dummyuser@zulip.com", "");

    await search_and_check(
        page,
        "pm-with:dummyuser@zulip.com",
        "",
        expect_non_existing_user,
        "Invalid user - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "pm-with:dummyuser@zulip.com,dummyuser2@zulip.com",
        "",
        expect_non_existing_users,
        "Invalid users - Zulip Dev - Zulip",
    );
}

async function expect_all_pm(page) {
    await page.waitForSelector("#zfilt", {visible: true});
    await common.check_messages_sent(page, "zfilt", [
        ["You and Cordelia Lear, King Hamlet", ["group pm a", "group pm b"]],
        ["You and Cordelia Lear", ["pm c"]],
        ["You and Cordelia Lear, King Hamlet", ["group pm d"]],
        ["You and Cordelia Lear", ["pm e"]],
    ]);
    assert.strictEqual(
        await common.get_text_from_selector(page, "#left_bar_compose_stream_button_big"),
        "New stream message",
    );
    assert.strictEqual(await page.title(), "Private messages - Zulip Dev - Zulip");
}

async function test_narrow_by_clicking_the_left_sidebar(page) {
    console.log("Narrowing with left sidebar");

    await page.click((await get_stream_li(page, "Verona")) + " a");
    await expect_verona_stream(page);

    await page.click(".top_left_all_messages a");
    await expect_home(page);

    await page.click(".top_left_private_messages a");
    await expect_all_pm(page);

    await un_narrow(page);
}

async function arrow(page, direction) {
    await page.keyboard.press(`Arrow${direction}`);
}

async function test_search_venice(page) {
    await page.evaluate(() => {
        $(".stream-list-filter")
            .expectOne()
            .trigger("focus")
            .val("vEnI") // Must be case insensitive.
            .trigger($.Event("input"))
            .trigger($.Event("click"));
    });

    await page.waitForSelector(await get_stream_li(page, "Denmark"), {hidden: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {hidden: true});
    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        visible: true,
    });

    // Clearing list gives back all the streams in the list
    await page.evaluate(() =>
        $(".stream-list-filter").expectOne().trigger("focus").val("").trigger($.Event("input")),
    );
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Venice"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {visible: true});

    await page.click("#streams_header .sidebar-title");
    await page.waitForSelector(".input-append.notdisplayed");
}

async function test_stream_search_filters_stream_list(page) {
    console.log("Search streams using left side bar");

    await page.waitForSelector(".input-append.notdisplayed"); // Stream filter box invisible initially
    await page.click("#streams_header .sidebar-title");

    await page.waitForSelector("#streams_list .input-append.notdisplayed", {hidden: true});

    // assert streams exist by waiting till they're visible
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Venice"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {visible: true});

    // Enter the search box and test highlighted suggestion
    await page.evaluate(() =>
        $(".stream-list-filter").expectOne().trigger("focus").trigger($.Event("click")),
    );

    await page.waitForSelector("#stream_filters .highlighted_stream", {visible: true});
    // First stream in list gets highlihted on clicking search.
    await page.waitForSelector((await get_stream_li(page, "Denmark")) + ".highlighted_stream", {
        visible: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Verona")) + ".highlighted_stream", {
        hidden: true,
    });

    // Navigate through suggesrions using arrow keys
    await arrow(page, "Down"); // Denmark -> Venice
    await arrow(page, "Up"); // Venice -> Denmark
    await arrow(page, "Up"); // Denmark -> Denmark
    await arrow(page, "Down"); // Denmark -> Venice

    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        visible: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Denmark")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Verona")) + ".highlighted_stream", {
        hidden: true,
    });

    await test_search_venice(page);

    // Search for brginning of "Verona".
    await page.evaluate(() =>
        $(".stream-list-filter").expectOne().trigger("focus").val("ver").trigger($.Event("input")),
    );
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {hidden: true});
    await page.click(await get_stream_li(page, "Verona"));
    await expect_verona_stream(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".stream-list-filter"),
        "",
        "Clicking on stream didn't clear search",
    );
    await un_narrow(page);
}

async function test_users_search(page) {
    console.log("Search users using right sidebar");
    async function assert_in_list(page, name) {
        await page.waitForSelector(`#user_presences li [data-name="${name}"]`, {visible: true});
    }

    async function assert_selected(page, name) {
        await page.waitForSelector(`#user_presences li.highlighted_user [data-name="${name}"]`, {
            visible: true,
        });
    }

    async function assert_not_selected(page, name) {
        await common.assert_selector_doesnt_exist(
            page,
            `#user_presences li.highlighted_user [data-name="${name}"]`,
        );
    }

    await assert_in_list(page, "Desdemona");
    await assert_in_list(page, "Cordelia Lear");
    await assert_in_list(page, "King Hamlet");
    await assert_in_list(page, "aaron");

    // Enter the search box and test selected suggestion navigation
    await page.evaluate(() =>
        $("#user_filter_icon").expectOne().trigger("focus").trigger($.Event("click")),
    );
    await page.waitForSelector("#user_presences .highlighted_user", {visible: true});
    await assert_selected(page, "Desdemona");
    await assert_not_selected(page, "Cordelia Lear");
    await assert_not_selected(page, "King Hamlet");
    await assert_not_selected(page, "aaron");

    // Navigate using arrow keys.
    // go down 2, up 3, then down 3
    //       Desdemona
    //       aaron
    //       Cordelia Lear
    //       Iago
    await arrow(page, "Down");
    await arrow(page, "Down");
    await arrow(page, "Up");
    await arrow(page, "Up");
    await arrow(page, "Up"); // does nothing; allready on the top.
    await arrow(page, "Down");
    await arrow(page, "Down");
    await arrow(page, "Down");

    // Now Iago must be highlighted
    await page.waitForSelector('#user_presences li.highlighted_user [data-name="Iago"]', {
        visible: true,
    });
    await assert_not_selected(page, "King Hamlet");
    await assert_not_selected(page, "aaron");
    await assert_not_selected(page, "Desdemona");

    // arrow up and press Enter. We should be taken to pms with Cordelia Lear
    await arrow(page, "Up");
    await page.keyboard.press("Enter");
    await expect_cordelia_private_narrow(page);
}

async function message_basic_tests(page) {
    await common.log_in(page);

    console.log("Sending messages");
    await common.send_multiple_messages(page, [
        {stream: "Verona", topic: "test", content: "verona test a"},
        {stream: "Verona", topic: "test", content: "verona test b"},
        {stream: "Verona", topic: "other topic", content: "verona other topic c"},
        {stream: "Denmark", topic: "test", content: "denmark message"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group pm a"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group pm b"},
        {recipient: "cordelia@zulip.com", content: "pm c"},
        {stream: "Verona", topic: "test", content: "verona test d"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group pm d"},
        {recipient: "cordelia@zulip.com", content: "pm e"},
    ]);

    await expect_home(page);

    await test_navigations_from_home(page);
    await search_tests(page);
    await test_narrow_by_clicking_the_left_sidebar(page);
    await test_stream_search_filters_stream_list(page);
    await test_users_search(page);

    await common.log_out(page);
}

common.run_test(message_basic_tests);
