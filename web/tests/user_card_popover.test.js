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

const people = zrequire("people");
const user_status = zrequire("user_status");
const user_card_popover = zrequire("user_card_popover");

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

function test_ui(label, f) {
    run_test(label, (handlers) => {
        page_params.is_admin = false;
        page_params.custom_profile_fields = [];
        user_card_popover.clear_for_testing();
        user_card_popover.initialize();
        f(handlers);
    });
}

test_ui("sender_hover", ({override, mock_template}) => {
    page_params.is_spectator = false;
    override($.fn, "popover", noop);

    const selection = ".sender_name, .message-avatar";
    const handler = $("#main_div").get_on_handler("click", selection);

    const message = {
        id: 999,
        sender_id: alice.user_id,
    };

    user_status.set_status_text({
        user_id: alice.user_id,
        status_text: "on the beach",
    });

    const status_emoji_info = {
        emoji_name: "car",
        emoji_code: "1f697",
        reaction_type: "unicode_emoji",
        emoji_alt_code: false,
    };
    user_status.set_status_emoji({user_id: alice.user_id, ...status_emoji_info});

    rows.id = () => message.id;

    message_lists.current.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    message_lists.current.select_id = (msg_id) => {
        assert.equal(msg_id, message.id);
    };

    const $target = $.create("click target");

    $target.closest = (sel) => {
        assert.equal(sel, ".message_row");
        return {};
    };

    mock_template("no_arrow_popover.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            class: "message-user-card-popover",
        });
        return "popover-html";
    });

    mock_template("user_card_popover_title.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            user_avatar: "http://zulip.zulipdev.com/avatar/42?s=50",
            user_is_guest: false,
        });
        return "title-html";
    });
    const $popover_content = $.create("content-html");
    mock_template("user_card_popover_content.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            invisible_mode: false,
            can_send_private_message: true,
            display_profile_fields: [],
            user_full_name: "Alice Smith",
            user_email: "alice-delivery@example.com",
            user_id: 42,
            user_time: undefined,
            user_type: $t({defaultMessage: "Member"}),
            user_circle_class: "user_circle_empty",
            user_last_seen_time_status: "translated: Active more than 2 weeks ago",
            pm_with_url: "#narrow/dm/42-Alice-Smith",
            sent_by_url: "#narrow/sender/42-Alice-Smith",
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
            user_mention_syntax: "@**Alice Smith**",
            date_joined: undefined,
            spectator_view: false,
        });
        return $popover_content;
    });

    $.create(".user_popover_email", {children: []});
    $("#userlist-title").get_offset_to_window = () => 10;
    $popover_content.get = () => {};
    const $user_name_element = $.create("user_full_name");
    const $bot_owner_element = $.create("bot_owner");
    $popover_content.set_find_results(".user_full_name", $user_name_element);
    $popover_content.set_find_results(".bot_owner", $bot_owner_element);

    const image_stubber = make_image_stubber();
    handler.call($target, e);

    const avatar_img = image_stubber.get(0);
    assert.equal(avatar_img.src.toString(), "/avatar/42/medium?version=5");

    // todo: load image
});
