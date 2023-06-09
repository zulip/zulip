"use strict";

const {strict: assert} = require("assert");

const {$t} = require("./lib/i18n");
const {mock_cjs, mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const noop = function () {};

class Clipboard {
    on() {}
}
mock_cjs("clipboard", Clipboard);

const rows = mock_esm("../src/rows");
mock_esm("../src/emoji_picker", {
    hide_emoji_popover: noop,
});
mock_esm("../src/giphy", {
    hide_giphy_popover: noop,
});
const message_lists = mock_esm("../src/message_lists", {
    current: {
        view: {
            message_containers: {},
        },
    },
});
mock_esm("../src/stream_popover", {
    hide_stream_popover: noop,
    hide_topic_popover: noop,
    hide_drafts_popover: noop,
    hide_streamlist_sidebar: noop,
});

set_global("document", {
    to_$: () => $("document-stub"),
});

function make_image_stubber() {
    const images = [];

    class Image {
        constructor() {
            images.push(this);
        }
        to_$() {
            return {
                on: (name, f) => {
                    assert.equal(name, "load");
                    this.load_f = f;
                },
            };
        }
    }

    set_global("Image", Image);

    return {
        get: (i) => images[i],
    };
}

const people = zrequire("people");
const user_status = zrequire("user_status");
const popovers = zrequire("popovers");

const alice = {
    email: "alice@example.com",
    delivery_email: "alice-delivery@example.com",
    full_name: "Alice Smith",
    user_id: 42,
    avatar_version: 5,
    is_guest: false,
    is_admin: false,
    role: 400,
    date_joined: "2021-11-01T16:32:16.458735+00:00",
};

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "America/Los_Angeles",
};

const e = {
    stopPropagation: noop,
};

function initialize_people() {
    people.init();
    people.add_active_user(me);
    people.add_active_user(alice);
    people.initialize_current_user(me.user_id);
}

initialize_people();

function make_image_stubber() {
    const images = [];

    class Image {
        constructor() {
            images.push(this);
        }
        to_$() {
            return {
                on: (name, f) => {
                    assert.equal(name, "load");
                    this.load_f = f;
                },
            };
        }
    }

    set_global("Image", Image);

    return {
        get: (i) => images[i],
    };
}

function test_personal_menu(label, f) {
    run_test(label, (handlers) => {
        page_params.is_admin = false;
        page_params.custom_profile_fields = [];
        popovers.clear_for_testing();
        popovers.register_click_handlers();
        f(handlers);
    });
}

test_personal_menu("user popover", ({mock_template}) => {
    page_params.is_spectator = false;
    const $popover_content = $.create("content-html");
    mock_template("user_info_popover_content.hbs", false, (opts) => {

        assert.deepEqual(opts, {
            invisible_mode: false,
            can_send_private_message: true,
            display_profile_fields: [],
            user_full_name: "Me Myself",
            user_email: "me@example.com",
            user_id: 30,
            user_time: undefined,
            user_type: $t({defaultMessage: "Member"}),
            user_circle_class: "user_circle_empty",
            user_last_seen_time_status: "translated: Active more than 2 weeks ago",
            pm_with_url: "#narrow/dm/30-Me-Myself",
            sent_by_url: "#narrow/sender/30-Me-Myself",
            private_message_class: "respond_personal_button",
            show_manage_menu: true,
            is_me: false,
            is_active: true,
            is_bot: undefined,
            is_sender_popover: true,
            has_message_context: true,
            status_content_available: true,
            status_text: "on the beach",
            status_emoji_info,
            user_mention_syntax: "@**Me Myself**",
            date_joined: undefined,
            spectator_view: false,
        });

        return $popover_content;
    });
    
    $.create(".user_profile_popover", {children: []});
    $("#userlist-title").get_offset_to_window = () => 10;
    $popover_content.get = () => {};
    const $user_name_element = $.create("user_full_name");
    $popover_content.set_find_results(".user_popover_email", $user_name_element);

    assert(!$user_name_element.hasClass("user_profile_popover"));
});
