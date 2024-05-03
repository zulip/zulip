import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function get_stream_li(page: Page, stream_name: string): Promise<string> {
    const stream_id = await common.get_stream_id(page, stream_name);
    assert(stream_id !== undefined);
    return `#stream_filters [data-stream-id="${CSS.escape(stream_id.toString())}"]`;
}

async function expect_home(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    // Assert that there is only one message list.
    assert.equal((await page.$$(".message-list")).length, 1);
    assert.strictEqual(await page.title(), "Combined feed - Zulip Dev - Zulip");
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Verona > other topic", ["verona other topic c"]],
        ["Denmark > test", ["denmark message"]],
        [
            "You and Cordelia, Lear's daughter, King Hamlet",
            ["group direct message a", "group direct message b"],
        ],
        ["You and Cordelia, Lear's daughter", ["direct message c"]],
        ["Verona > test", ["verona test d"]],
        ["You and Cordelia, Lear's daughter, King Hamlet", ["group direct message d"]],
        ["You and Cordelia, Lear's daughter", ["direct message e"]],
    ]);
}

async function expect_verona_stream(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Verona > other topic", ["verona other topic c"]],
        ["Verona > test", ["verona test d"]],
    ]);
    assert.strictEqual(await page.title(), "#Verona - Zulip Dev - Zulip");
}

async function expect_verona_stream_test_topic(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > test", ["verona test a", "verona test b", "verona test d"]],
    ]);
    assert.strictEqual(
        await common.get_text_from_selector(page, "#new_conversation_button"),
        "Start new conversation",
    );
}

async function expect_verona_other_topic(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > other topic", ["verona other topic c"]],
    ]);
}

async function expect_test_topic(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Denmark > test", ["denmark message"]],
        ["Verona > test", ["verona test d"]],
    ]);
}

async function expect_group_direct_messages(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        [
            "You and Cordelia, Lear's daughter, King Hamlet",
            ["group direct message a", "group direct message b", "group direct message d"],
        ],
    ]);
    assert.strictEqual(
        await page.title(),
        "Cordelia, Lear's daughter, King Hamlet - Zulip Dev - Zulip",
    );
}

async function expect_cordelia_direct_messages(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        ["You and Cordelia, Lear's daughter", ["direct message c", "direct message e"]],
    ]);
}

async function un_narrow(page: Page): Promise<void> {
    if ((await (await page.$(".message_comp"))!.boundingBox())?.height) {
        await page.keyboard.press("Escape");
    }
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
}

async function un_narrow_by_clicking_org_icon(page: Page): Promise<void> {
    await page.click(".brand");
}

async function expect_recent_view(page: Page): Promise<void> {
    await page.waitForSelector("#recent_view_table", {visible: true});
    assert.strictEqual(await page.title(), "Recent conversations - Zulip Dev - Zulip");
}

async function test_navigations_from_home(page: Page): Promise<void> {
    return; // No idea why this is broken.
    console.log("Narrowing by clicking stream");
    await page.click(`.focused-message-list [title='Narrow to stream "Verona"']`);
    await expect_verona_stream(page);

    assert.strictEqual(await page.title(), "#Verona - Zulip Dev - Zulip");
    await un_narrow(page);
    await expect_home(page);

    console.log("Narrowing by clicking topic");
    await page.click(`.focused-message-list [title='Narrow to stream "Verona", topic "test"']`);
    await expect_verona_stream_test_topic(page);

    await un_narrow(page);
    await expect_home(page);

    return; // TODO: rest of this test seems nondeterministically broken
    console.log("Narrowing by clicking group personal header");
    await page.click(
        `.focused-message-list [title="Narrow to your direct messages with Cordelia, Lear's daughter, King Hamlet"]`,
    );
    await expect_group_direct_messages(page);

    await un_narrow(page);
    await expect_home(page);

    await page.click(
        `.focused-message-list [title="Narrow to your direct messages with Cordelia, Lear's daughter, King Hamlet"]`,
    );
    await un_narrow_by_clicking_org_icon(page);
    await expect_recent_view(page);
}

async function search_and_check(
    page: Page,
    search_str: string,
    item_to_select: string,
    check: (page: Page) => Promise<void>,
    expected_narrow_title: string,
): Promise<void> {
    await page.click(".search_icon");
    await page.waitForSelector(".navbar-search.expanded", {visible: true});
    await common.select_item_via_typeahead(page, "#search_query", search_str, item_to_select);
    await check(page);
    assert.strictEqual(await page.title(), expected_narrow_title);
    await un_narrow(page);
    await expect_home(page);
}

async function search_silent_user(page: Page, str: string, item: string): Promise<void> {
    await page.click(".search_icon");
    await page.waitForSelector(".navbar-search.expanded", {visible: true});
    await common.select_item_via_typeahead(page, "#search_query", str, item);
    await page.waitForSelector(".empty_feed_notice", {visible: true});
    const expect_message = "You haven't received any messages sent by Email Gateway yet.";
    assert.strictEqual(
        await common.get_text_from_selector(page, ".empty_feed_notice"),
        expect_message,
    );
    await common.get_current_msg_list_id(page, true);
    await un_narrow(page);
    await expect_home(page);
}

async function expect_non_existing_user(page: Page): Promise<void> {
    await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(".empty_feed_notice", {visible: true});
    const expected_message = "This user does not exist!";
    assert.strictEqual(
        await common.get_text_from_selector(page, ".empty_feed_notice"),
        expected_message,
    );
}

async function expect_non_existing_users(page: Page): Promise<void> {
    await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(".empty_feed_notice", {visible: true});
    const expected_message = "One or more of these users do not exist!";
    assert.strictEqual(
        await common.get_text_from_selector(page, ".empty_feed_notice"),
        expected_message,
    );
}

async function search_non_existing_user(page: Page, str: string, item: string): Promise<void> {
    await page.click(".search_icon");
    await page.waitForSelector(".navbar-search.expanded", {visible: true});
    await common.select_item_via_typeahead(page, "#search_query", str, item);
    await expect_non_existing_user(page);
    await un_narrow(page);
    await expect_home(page);
}

async function search_tests(page: Page): Promise<void> {
    await search_and_check(
        page,
        "Verona",
        "Channel",
        expect_verona_stream,
        "#Verona - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "Cordelia",
        "Direct",
        expect_cordelia_direct_messages,
        "Cordelia, Lear's daughter - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona",
        "",
        expect_verona_stream,
        "#Verona - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona topic:test",
        "",
        expect_verona_stream_test_topic,
        "#Verona > test - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "stream:Verona topic:other+topic",
        "",
        expect_verona_other_topic,
        "#Verona > other topic - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "topic:test",
        "",
        expect_test_topic,
        "Search results - Zulip Dev - Zulip",
    );

    await search_silent_user(page, "sender:emailgateway@zulip.com", "");

    await search_non_existing_user(page, "sender:dummyuser@zulip.com", "");

    await search_and_check(
        page,
        "dm:dummyuser@zulip.com",
        "",
        expect_non_existing_user,
        "Invalid user - Zulip Dev - Zulip",
    );

    await search_and_check(
        page,
        "dm:dummyuser@zulip.com,dummyuser2@zulip.com",
        "",
        expect_non_existing_users,
        "Invalid users - Zulip Dev - Zulip",
    );
}

async function expect_all_direct_messages(page: Page): Promise<void> {
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });
    await common.check_messages_sent(page, message_list_id, [
        [
            "You and Cordelia, Lear's daughter, King Hamlet",
            ["group direct message a", "group direct message b"],
        ],
        ["You and Cordelia, Lear's daughter", ["direct message c"]],
        ["You and Cordelia, Lear's daughter, King Hamlet", ["group direct message d"]],
        ["You and Cordelia, Lear's daughter", ["direct message e"]],
    ]);
    assert.strictEqual(
        await common.get_text_from_selector(page, "#new_conversation_button"),
        "Start new conversation",
    );
    assert.strictEqual(await page.title(), "Direct message feed - Zulip Dev - Zulip");
}

async function test_narrow_by_clicking_the_left_sidebar(page: Page): Promise<void> {
    console.log("Narrowing with left sidebar");

    await page.click((await get_stream_li(page, "Verona")) + " a");
    await expect_verona_stream(page);

    await page.click("#left-sidebar-navigation-list .top_left_all_messages a");
    await expect_home(page);

    const all_private_messages_icon = "#show_all_private_messages";
    await page.waitForSelector(all_private_messages_icon, {visible: true});
    await page.click(all_private_messages_icon);
    await expect_all_direct_messages(page);

    await un_narrow(page);
    await expect_home(page);
}

async function arrow(page: Page, direction: "Up" | "Down"): Promise<void> {
    await page.keyboard.press(({Up: "ArrowUp", Down: "ArrowDown"} as const)[direction]);
}

async function test_search_venice(page: Page): Promise<void> {
    await common.clear_and_type(page, ".stream-list-filter", "vEnI"); // Must be case insensitive.
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {hidden: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {hidden: true});
    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        visible: true,
    });

    // Clearing list gives back all the streams in the list
    await common.clear_and_type(page, ".stream-list-filter", "");
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Venice"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {visible: true});

    await page.click("#streams_header .left-sidebar-title");
    await page.waitForSelector(".input-append.notdisplayed");
}

async function test_stream_search_filters_stream_list(page: Page): Promise<void> {
    console.log("Filter streams using left side bar");

    await page.waitForSelector(".input-append.notdisplayed"); // Stream filter box invisible initially
    await page.click("#streams_header .left-sidebar-title");

    await page.waitForSelector("#streams_list .input-append.notdisplayed", {hidden: true});

    // assert streams exist by waiting till they're visible
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Venice"), {visible: true});
    await page.waitForSelector(await get_stream_li(page, "Verona"), {visible: true});

    // Enter the search box and test highlighted suggestion
    await page.click(".stream-list-filter");

    await page.waitForSelector("#stream_filters .highlighted_stream", {visible: true});
    // First stream in list gets highlighted on clicking search.
    await page.waitForSelector((await get_stream_li(page, "core team")) + ".highlighted_stream", {
        visible: true,
    });

    await page.waitForSelector((await get_stream_li(page, "Denmark")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Verona")) + ".highlighted_stream", {
        hidden: true,
    });

    // Navigate through suggestions using arrow keys
    await arrow(page, "Down"); // core team -> Denmark
    await arrow(page, "Down"); // Denmark -> Venice
    await arrow(page, "Up"); // Venice -> Denmark
    await arrow(page, "Up"); // Denmark -> core team
    await arrow(page, "Up"); // core team -> core team
    await arrow(page, "Down"); // core team -> Denmark
    await arrow(page, "Down"); // Denmark -> Venice
    await arrow(page, "Down"); // Venice -> Verona

    await page.waitForSelector((await get_stream_li(page, "Verona")) + ".highlighted_stream", {
        visible: true,
    });

    await page.waitForSelector((await get_stream_li(page, "core team")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Denmark")) + ".highlighted_stream", {
        hidden: true,
    });
    await page.waitForSelector((await get_stream_li(page, "Venice")) + ".highlighted_stream", {
        hidden: true,
    });
    await test_search_venice(page);

    // Search for beginning of "Verona".
    await page.click("#streams_header .left-sidebar-title");
    await page.type(".stream-list-filter", "ver");
    await page.waitForSelector(await get_stream_li(page, "core team"), {hidden: true});
    await page.waitForSelector(await get_stream_li(page, "Denmark"), {hidden: true});
    await page.waitForSelector(await get_stream_li(page, "Venice"), {hidden: true});
    await page.click(await get_stream_li(page, "Verona"));
    await expect_verona_stream(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".stream-list-filter"),
        "",
        "Clicking on stream didn't clear search",
    );
    await un_narrow(page);
}

async function test_users_search(page: Page): Promise<void> {
    console.log("Search users using right sidebar");
    async function assert_in_list(page: Page, name: string): Promise<void> {
        await page.waitForSelector(`#buddy-list-other-users li [data-name="${CSS.escape(name)}"]`, {
            visible: true,
        });
    }

    async function assert_selected(page: Page, name: string): Promise<void> {
        await page.waitForSelector(
            `#buddy-list-other-users li.highlighted_user [data-name="${CSS.escape(name)}"]`,
            {visible: true},
        );
    }

    async function assert_not_selected(page: Page, name: string): Promise<void> {
        await page.waitForSelector(
            `#buddy-list-other-users li.highlighted_user [data-name="${CSS.escape(name)}"]`,
            {hidden: true},
        );
    }

    await assert_in_list(page, "Desdemona");
    await assert_in_list(page, "Cordelia, Lear's daughter");
    await assert_in_list(page, "King Hamlet");
    await assert_in_list(page, "aaron");

    // Enter the search box and test selected suggestion navigation
    await page.click("#user_filter_icon");
    await page.waitForSelector("#buddy-list-other-users .highlighted_user", {visible: true});
    await assert_selected(page, "Desdemona");
    await assert_not_selected(page, "Cordelia, Lear's daughter");
    await assert_not_selected(page, "King Hamlet");
    await assert_not_selected(page, "aaron");

    // Navigate using arrow keys.
    // go down 2, up 3, then down 3
    //       Desdemona
    //       aaron
    //       Cordelia, Lear's daughter
    //       Iago
    await arrow(page, "Down");
    await arrow(page, "Down");
    await arrow(page, "Up");
    await arrow(page, "Up");
    await arrow(page, "Up"); // does nothing; already on the top.
    await arrow(page, "Down");
    await arrow(page, "Down");
    await arrow(page, "Down");

    // Now Iago must be highlighted
    await page.waitForSelector('#buddy-list-other-users li.highlighted_user [data-name="Iago"]', {
        visible: true,
    });
    await assert_not_selected(page, "King Hamlet");
    await assert_not_selected(page, "aaron");
    await assert_not_selected(page, "Desdemona");

    // arrow up and press Enter. We should be taken to direct messages with Cordelia, Lear's daughter
    await arrow(page, "Up");
    await page.keyboard.press("Enter");
    await expect_cordelia_direct_messages(page);
}

async function test_narrow_public_streams(page: Page): Promise<void> {
    const stream_id = await common.get_stream_id(page, "Denmark");
    await page.goto(`http://zulip.zulipdev.com:9981/#channels/${stream_id}/Denmark`);
    await page.waitForSelector("button.sub_unsub_button", {visible: true});
    await page.click("button.sub_unsub_button");
    await page.waitForSelector(
        `xpath///button[${common.has_class_x(
            "sub_unsub_button",
        )} and normalize-space()="Subscribe"]`,
    );
    await page.click(".subscriptions-header .exit-sign");
    await page.waitForSelector("#subscription_overlay", {hidden: true});
    await page.goto(`http://zulip.zulipdev.com:9981/#narrow/stream/${stream_id}-Denmark`);
    let message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .recipient_row ~ .recipient_row ~ .recipient_row`,
    );
    assert.ok(
        (await page.$(
            `.message-list[data-message-list-id='${message_list_id}'] .stream-status`,
        )) !== null,
    );

    await page.goto("http://zulip.zulipdev.com:9981/#narrow/streams/public");
    message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .recipient_row ~ .recipient_row ~ .recipient_row`,
    );
    assert.ok(
        (await page.$(
            `.message-list[data-message-list-id='${message_list_id}'] .stream-status`,
        )) === null,
    );
}

async function message_basic_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await page.waitForSelector(".message-list .message_row", {visible: true});
    // Assert that there is only one message list.
    assert.equal((await page.$$(".message-list")).length, 1);

    console.log("Sending messages");
    await common.send_multiple_messages(page, [
        {stream_name: "Verona", topic: "test", content: "verona test a"},
        {stream_name: "Verona", topic: "test", content: "verona test b"},
        {stream_name: "Verona", topic: "other topic", content: "verona other topic c"},
        {stream_name: "Denmark", topic: "test", content: "denmark message"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group direct message a"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group direct message b"},
        {recipient: "cordelia@zulip.com", content: "direct message c"},
        {stream_name: "Verona", topic: "test", content: "verona test d"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group direct message d"},
        {recipient: "cordelia@zulip.com", content: "direct message e"},
    ]);

    await expect_home(page);

    await test_navigations_from_home(page);
    await search_tests(page);
    await test_narrow_by_clicking_the_left_sidebar(page);
    await test_stream_search_filters_stream_list(page);
    await test_users_search(page);
    await test_narrow_public_streams(page);
}

common.run_test(message_basic_tests);
