"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_message_list} = require("./lib/message_list.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const state_data = zrequire("state_data");
const stream_list_sort = zrequire("stream_list_sort");
const settings_config = zrequire("settings_config");
const stream_topic_history = zrequire("stream_topic_history");
const message_lists = zrequire("message_lists");
const channel_folders = zrequire("channel_folders");
const {initialize_user_settings} = zrequire("user_settings");

state_data.set_realm(
    make_realm({
        realm_empty_topic_display_name: "general chat",
    }),
);

// Start with always filtering out inactive streams.
const user_settings = {
    demote_inactive_streams: settings_config.demote_inactive_streams_values.always.code,
};
initialize_user_settings({user_settings});
stream_list_sort.set_filter_out_inactives();

const frontend_folder = {
    name: "Frontend",
    description: "Channels for frontend discussions",
    rendered_description: "<p>Channels for frontend discussions</p>",
    creator_id: null,
    date_created: 1596710000,
    id: 1,
    is_archived: false,
    order: 2,
};
const backend_folder = {
    name: "Backend",
    description: "Channels for backend discussions",
    rendered_description: "<p>Channels for backend discussions</p>",
    creator_id: null,
    date_created: 1596720000,
    id: 2,
    is_archived: false,
    order: 1,
};

const scalene = make_stream({
    subscribed: true,
    name: "scalene",
    stream_id: 1,
    pin_to_top: true,
    is_recently_active: true,
    folder_id: frontend_folder.id,
});
const fast_tortoise = make_stream({
    subscribed: true,
    name: "fast tortoise",
    stream_id: 2,
    pin_to_top: false,
    is_recently_active: true,
    folder_id: frontend_folder.id,
});
const pneumonia = make_stream({
    subscribed: true,
    name: "pneumonia",
    stream_id: 3,
    pin_to_top: false,
    is_recently_active: false,
    folder_id: frontend_folder.id,
});
const clarinet = make_stream({
    subscribed: true,
    name: "clarinet",
    stream_id: 4,
    pin_to_top: false,
    is_recently_active: true,
});
const weaving = make_stream({
    subscribed: false,
    name: "weaving",
    stream_id: 5,
    pin_to_top: false,
    is_recently_active: true,
});
const stream_hyphen_underscore_slash_colon = make_stream({
    subscribed: true,
    name: "stream-hyphen_underscore/slash:colon",
    stream_id: 6,
    pin_to_top: false,
    is_recently_active: true,
    folder_id: backend_folder.id,
});
const muted_active = make_stream({
    subscribed: true,
    name: "muted active",
    stream_id: 7,
    pin_to_top: false,
    is_recently_active: true,
    is_muted: true,
    folder_id: frontend_folder.id,
});
const muted_pinned = make_stream({
    subscribed: true,
    name: "muted pinned",
    stream_id: 8,
    pin_to_top: true,
    is_recently_active: true,
    is_muted: true,
});
const archived = make_stream({
    subscribed: true,
    name: "archived channel",
    stream_id: 9,
    pin_to_top: true,
    is_archived: true,
});

channel_folders.initialize({
    channel_folders: [frontend_folder, backend_folder],
});

function add_all_subs() {
    stream_data.add_sub_for_tests(scalene);
    stream_data.add_sub_for_tests(fast_tortoise);
    stream_data.add_sub_for_tests(pneumonia);
    stream_data.add_sub_for_tests(clarinet);
    stream_data.add_sub_for_tests(weaving);
    stream_data.add_sub_for_tests(stream_hyphen_underscore_slash_colon);
    stream_data.add_sub_for_tests(muted_active);
    stream_data.add_sub_for_tests(muted_pinned);
    stream_data.add_sub_for_tests(archived);
}

function sort_groups(query) {
    const streams = stream_data.subscribed_stream_ids();
    return stream_list_sort.sort_groups(streams, query);
}

function test(label, f) {
    run_test(label, (helpers) => {
        stream_data.clear_subscriptions();
        f(helpers);
    });
}

test("no_subscribed_streams", () => {
    const sorted = sort_groups("");
    assert.deepEqual(sorted, {
        sections: [
            {
                id: "pinned-streams",
                folder_id: null,
                inactive_streams: [],
                muted_streams: [],
                section_title: "translated: PINNED CHANNELS",
                streams: [],
            },
            {
                id: "normal-streams",
                folder_id: null,
                inactive_streams: [],
                muted_streams: [],
                section_title: "translated: CHANNELS",
                streams: [],
            },
        ],
        same_as_before: sorted.same_as_before,
    });
});

test("basics", ({override}) => {
    add_all_subs();

    // Test sorting into categories/alphabetized
    let sorted_sections = sort_groups("").sections;
    const pinned = sorted_sections[0];
    assert.deepEqual(pinned.id, "pinned-streams");
    assert.deepEqual(pinned.streams, [scalene.stream_id]);
    assert.deepEqual(pinned.muted_streams, [muted_pinned.stream_id]);
    const normal = sorted_sections[1];
    assert.deepEqual(normal.id, "normal-streams");
    assert.deepEqual(normal.streams, [
        clarinet.stream_id,
        fast_tortoise.stream_id,
        stream_hyphen_underscore_slash_colon.stream_id,
    ]);
    assert.deepEqual(normal.muted_streams, [muted_active.stream_id]);
    assert.deepEqual(normal.inactive_streams, [pneumonia.stream_id]);

    assert.deepEqual(stream_list_sort.get_stream_ids(), [
        scalene.stream_id,
        muted_pinned.stream_id,
        clarinet.stream_id,
        fast_tortoise.stream_id,
        stream_hyphen_underscore_slash_colon.stream_id,
        muted_active.stream_id,
        pneumonia.stream_id,
    ]);

    assert.equal(
        stream_list_sort.current_section_id_for_stream(scalene.stream_id),
        "pinned-streams",
    );
    assert.equal(
        stream_list_sort.current_section_id_for_stream(clarinet.stream_id),
        "normal-streams",
    );

    // Test filtering
    sorted_sections = sort_groups("s").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].id, "pinned-streams");
    assert.deepEqual(sorted_sections[0].streams, [scalene.stream_id]);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);

    // Test searching entire word, case-insensitive
    sorted_sections = sort_groups("PnEuMoNiA").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].streams, []);
    assert.deepEqual(sorted_sections[1].inactive_streams, [pneumonia.stream_id]);

    // Test searching part of word
    sorted_sections = sort_groups("tortoise").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].streams, [fast_tortoise.stream_id]);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);

    // Test searching stream with spaces
    sorted_sections = sort_groups("fast t").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].streams, [fast_tortoise.stream_id]);

    // Test searching part of stream name with non space word separators
    sorted_sections = sort_groups("hyphen").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);

    sorted_sections = sort_groups("hyphen_underscore").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);

    sorted_sections = sort_groups("colon").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);

    sorted_sections = sort_groups("underscore").sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].id, "normal-streams");
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);

    override(user_settings, "web_left_sidebar_show_channel_folders", true);
    sorted_sections = sort_groups("").sections;
    assert.deepEqual(sorted_sections.length, 4);
    assert.deepEqual(sorted_sections[0].id, "pinned-streams");
    assert.deepEqual(sorted_sections[0].section_title, "translated: PINNED CHANNELS");
    assert.deepEqual(sorted_sections[1].id, "2");
    assert.deepEqual(sorted_sections[1].section_title, "BACKEND");
    assert.deepEqual(sorted_sections[2].id, "1");
    assert.deepEqual(sorted_sections[2].section_title, "FRONTEND");
    assert.deepEqual(sorted_sections[3].id, "normal-streams");
    assert.deepEqual(sorted_sections[3].section_title, "translated: OTHER");

    // If both `pin_to_top` is true and folder_id is set, as in
    // the channel `scalene`, then the channel ends up in the pinned
    // section and `folder_id` is ignored.
    assert.deepEqual(sorted_sections[0].streams, [scalene.stream_id]);
    assert.deepEqual(sorted_sections[0].muted_streams, [muted_pinned.stream_id]);
    assert.deepEqual(sorted_sections[0].inactive_streams, []);
    assert.deepEqual(sorted_sections[1].streams, [stream_hyphen_underscore_slash_colon.stream_id]);
    assert.deepEqual(sorted_sections[1].muted_streams, []);
    assert.deepEqual(sorted_sections[1].inactive_streams, []);
    assert.deepEqual(sorted_sections[2].streams, [fast_tortoise.stream_id]);
    assert.deepEqual(sorted_sections[2].muted_streams, [muted_active.stream_id]);
    assert.deepEqual(sorted_sections[2].inactive_streams, [pneumonia.stream_id]);
    assert.deepEqual(sorted_sections[3].streams, [clarinet.stream_id]);
    assert.deepEqual(sorted_sections[3].muted_streams, []);
    assert.deepEqual(sorted_sections[3].inactive_streams, []);

    // The first and last sections are invariant. The intermediate sections
    // are arranged by the `order` field in the channel folder object.
    assert.deepEqual(stream_list_sort.section_ids(), [
        "pinned-streams",
        "2",
        "1",
        "normal-streams",
    ]);
});

test("current_section_id_for_stream", ({override}) => {
    override(user_settings, "web_left_sidebar_show_channel_folders", false);
    add_all_subs();

    sort_groups("");
    assert.equal(
        stream_list_sort.current_section_id_for_stream(scalene.stream_id),
        "pinned-streams",
    );
    for (const stream_id of [
        clarinet.stream_id,
        fast_tortoise.stream_id,
        stream_hyphen_underscore_slash_colon.stream_id,
    ]) {
        assert.equal(stream_list_sort.current_section_id_for_stream(stream_id), "normal-streams");
    }

    override(user_settings, "web_left_sidebar_show_channel_folders", true);
    sort_groups("");
    // Now fast_tortoise should appear in its respective folder.
    assert.equal(
        stream_list_sort.current_section_id_for_stream(scalene.stream_id),
        "pinned-streams",
    );
    assert.equal(
        stream_list_sort.current_section_id_for_stream(clarinet.stream_id),
        "normal-streams",
    );
    assert.equal(
        stream_list_sort.current_section_id_for_stream(fast_tortoise.stream_id),
        String(frontend_folder.id),
    );
    assert.equal(
        stream_list_sort.current_section_id_for_stream(
            stream_hyphen_underscore_slash_colon.stream_id,
        ),
        String(backend_folder.id),
    );
});

test("left_sidebar_search", ({override}) => {
    // If a topic in the current channel matches the search query,
    // the channel should appear in its corresponding section in the result.
    add_all_subs();

    function setup_search_around_stream(stream) {
        message_lists.set_current(
            make_message_list([{operator: "stream", operand: stream.stream_id}]),
        );
        const history = stream_topic_history.find_or_create(stream.stream_id);
        history.add_or_update("an important topic", 1);
        return stream_list_sort.sort_groups(
            stream_data.subscribed_stream_ids().filter((id) => id !== stream.stream_id),
            "import",
        ).sections;
    }
    let sorted_sections = setup_search_around_stream(scalene);
    // The topic matches the search query, so the stream appears in the search result.
    // Since `pin_to_top` is true for scalene, it should be in that section.
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, [scalene.stream_id]);

    sorted_sections = stream_list_sort.sort_groups(
        stream_data.subscribed_stream_ids().filter((id) => id !== scalene.stream_id),
        "any",
    ).sections;
    assert.deepEqual(sorted_sections.length, 2);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[1].streams, []);

    // Testing the same for custom sections.
    override(user_settings, "web_left_sidebar_show_channel_folders", true);
    sorted_sections = setup_search_around_stream(fast_tortoise);
    // Since no channel in the section `BACKEND` matched the query, it
    // didn't make it to here.
    assert.deepEqual(sorted_sections.length, 3);
    assert.deepEqual(sorted_sections[1].folder_id, fast_tortoise.folder_id);
    assert.deepEqual(sorted_sections[1].streams, [fast_tortoise.stream_id]);
    assert.deepEqual(sorted_sections[0].streams, []);
    assert.deepEqual(sorted_sections[2].streams, []);
});

test("filter inactives", ({override}) => {
    // Test that we automatically switch to filtering out inactive streams
    // once the user has more than 30 streams.
    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.automatic.code,
    );

    stream_list_sort.set_filter_out_inactives();
    assert.ok(!stream_list_sort.is_filtering_inactives());

    _.times(30, (i) => {
        const name = "random" + i.toString();
        const stream_id = 100 + i;

        const sub = {
            name,
            subscribed: true,
            newly_subscribed: false,
            stream_id,
        };
        stream_data.add_sub_for_tests(sub);
    });
    stream_list_sort.set_filter_out_inactives();

    assert.ok(stream_list_sort.is_filtering_inactives());

    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.never.code,
    );
    stream_list_sort.set_filter_out_inactives();
    assert.ok(!stream_list_sort.is_filtering_inactives());
    // Even inactive channels are marked active.
    assert.ok(!pneumonia.is_recently_active);
    assert.ok(stream_list_sort.has_recent_activity(pneumonia));
});

test("initialize", ({override}) => {
    override(user_settings, "demote_inactive_streams", 1);
    stream_list_sort.initialize();

    assert.ok(!stream_list_sort.is_filtering_inactives());
});
