"use strict";

const {strict: assert} = require("assert");

const {$t} = require("../zjsunit/i18n");
const {mock_esm, set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const noop = function () {};

const rows = mock_esm("../../static/js/rows");
const stream_data = mock_esm("../../static/js/stream_data");
mock_esm("../../static/js/emoji_picker", {
    hide_emoji_popover: noop,
});
mock_esm("../../static/js/giphy", {
    hide_giphy_popover: noop,
});
const message_lists = mock_esm("../../static/js/message_lists", {
    current: {
        view: {
            message_containers: {},
        },
    },
});
mock_esm("../../static/js/message_viewport", {
    height: () => 500,
});
mock_esm("../../static/js/stream_popover", {
    hide_stream_popover: noop,
    hide_topic_popover: noop,
    hide_all_messages_popover: noop,
    hide_starred_messages_popover: noop,
    hide_streamlist_sidebar: noop,
});

const people = zrequire("people");
const user_status = zrequire("user_status");
const message_edit = zrequire("message_edit");
const emoji = zrequire("../shared/js/emoji");

// Bypass some scary code that runs when we import the module.
const popovers = with_field($.fn, "popover", noop, () => zrequire("popovers"));

const alice = {
    email: "alice@example.com",
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

    function stub_image() {
        const image = {};
        image.to_$ = () => ({
            on: (name, f) => {
                assert.equal(name, "load");
                image.load_f = f;
            },
        });
        images.push(image);
        return image;
    }

    set_global("Image", stub_image);

    return {
        get: (i) => images[i],
    };
}

function test_ui(label, f) {
    run_test(label, ({override, mock_template}) => {
        page_params.is_admin = false;
        page_params.realm_email_address_visibility = 3;
        page_params.custom_profile_fields = [];
        override(popovers, "clipboard_enable", () => ({
            on: noop,
        }));
        popovers.clear_for_testing();
        popovers.register_click_handlers();
        f({override, mock_template});
    });
}

test_ui("sender_hover", ({override, mock_template}) => {
    page_params.is_spectator = false;
    override($.fn, "popover", noop);
    override(emoji, "get_emoji_details_by_name", noop);

    const selection = ".sender_name, .sender_name-in-status, .inline_profile_picture";
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

    const target = $.create("click target");

    target.closest = (sel) => {
        assert.equal(sel, ".message_row");
        return {};
    };

    mock_template("no_arrow_popover.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            class: "message-info-popover",
        });
        return "popover-html";
    });

    mock_template("user_info_popover_title.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            user_avatar: "http://zulip.zulipdev.com/avatar/42?s=50",
            user_is_guest: false,
        });
        return "title-html";
    });

    mock_template("user_info_popover_content.hbs", false, (opts) => {
        assert.deepEqual(opts, {
            can_set_away: false,
            can_revoke_away: false,
            can_mute: true,
            can_unmute: false,
            user_full_name: "Alice Smith",
            user_email: "alice@example.com",
            user_id: 42,
            user_time: undefined,
            user_type: $t({defaultMessage: "Member"}),
            user_circle_class: "user_circle_empty",
            user_last_seen_time_status:
                "translated: Last active: translated: More than 2 weeks ago",
            pm_with_uri: "#narrow/pm-with/42-alice",
            sent_by_uri: "#narrow/sender/42-alice",
            private_message_class: "respond_personal_button",
            show_email: false,
            show_user_profile: true,
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
        return "content-html";
    });

    $.create(".user_popover_email", {children: []});
    const image_stubber = make_image_stubber();
    const base_url = window.location.href;
    handler.call(target, e);

    const avatar_img = image_stubber.get(0);
    const expected_url = new URL("avatar/42/medium?v=" + alice.avatar_version, base_url);
    assert.equal(avatar_img.src.toString(), expected_url.toString());

    // todo: load image
});

test_ui("actions_popover", ({override, mock_template}) => {
    override($.fn, "popover", noop);

    const target = $.create("click target");

    const handler = $("#main_div").get_on_handler("click", ".actions_hover");

    const message = {
        id: 999,
        topic: "Actions (1)",
        type: "stream",
        stream_id: 123,
    };

    message_lists.current.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    message_lists.current.view.message_containers.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return {
            is_hidden: false,
        };
    };

    override(message_edit, "get_editability", () => 4);

    stream_data.id_to_slug = (stream_id) => {
        assert.equal(stream_id, 123);
        return "Bracket ( stream";
    };

    target.closest = (sel) => {
        assert.equal(sel, ".message_row");
        return {
            toggleClass: noop,
        };
    };

    mock_template("actions_popover_content.hbs", false, (opts) => {
        // TODO: Test all the properties of the popover
        assert.equal(
            opts.conversation_time_uri,
            "http://zulip.zulipdev.com/#narrow/stream/Bracket.20.28.20stream/topic/Actions.20.281.29/near/999",
        );
        return "actions-content";
    });

    handler.call(target, e);
});
