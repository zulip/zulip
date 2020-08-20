"use strict";

const rewiremock = require("rewiremock/node");

set_global("$", global.make_zjquery());

zrequire("hash_util");
zrequire("narrow");
zrequire("narrow_state");
const people = zrequire("people");
zrequire("presence");
zrequire("buddy_data");
zrequire("user_status");
zrequire("feature_flags");
zrequire("message_edit");

const noop = function () {};
$.fn.popover = noop; // this will get wrapped by our code

set_global("current_msg_list", {});
set_global("page_params", {
    is_admin: false,
    realm_email_address_visibility: 3,
    custom_profile_fields: [],
});
set_global("rows", {});

set_global("message_viewport", {
    height: () => 500,
});

set_global("emoji_picker", {
    hide_emoji_popover: noop,
});

set_global("stream_popover", {
    hide_stream_popover: noop,
    hide_topic_popover: noop,
    hide_all_messages_popover: noop,
    hide_starred_messages_popover: noop,
    hide_streamlist_sidebar: noop,
});

set_global("stream_data", {});

function ClipboardJS(sel) {
    assert.equal(sel, ".copy_link");
}

rewiremock.proxy(() => zrequire("popovers"), {
    clipboard: ClipboardJS,
});

const alice = {
    email: "alice@example.com",
    full_name: "Alice Smith",
    user_id: 42,
    avatar_version: 5,
    is_guest: false,
    is_admin: false,
};

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "US/Pacific",
};

const target = $.create("click target");
target.offset = () => ({
    top: 10,
});

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

popovers.register_click_handlers();

run_test("sender_hover", (override) => {
    override("popovers.hide_user_profile", noop);

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

    rows.id = () => message.id;

    current_msg_list.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    current_msg_list.select_id = (msg_id) => {
        assert.equal(msg_id, message.id);
    };

    target.closest = (sel) => {
        assert.equal(sel, ".message_row");
        return {};
    };

    global.stub_templates((fn, opts) => {
        switch (fn) {
            case "no_arrow_popover":
                assert.deepEqual(opts, {
                    class: "message-info-popover",
                });
                return "popover-html";

            case "user_info_popover_title":
                assert.deepEqual(opts, {
                    user_avatar: "avatar/alice@example.com",
                    user_is_guest: false,
                });
                return "title-html";

            case "user_info_popover_content":
                assert.deepEqual(opts, {
                    can_set_away: false,
                    can_revoke_away: false,
                    user_full_name: "Alice Smith",
                    user_email: "alice@example.com",
                    user_id: 42,
                    user_time: undefined,
                    user_type: i18n.t("Member"),
                    user_circle_class: "user_circle_empty",
                    user_last_seen_time_status: "translated: More than 2 weeks ago",
                    pm_with_uri: "#narrow/pm-with/42-alice",
                    sent_by_uri: "#narrow/sender/42-alice",
                    private_message_class: "respond_personal_button",
                    show_email: false,
                    show_user_profile: false,
                    is_me: false,
                    is_active: true,
                    is_bot: undefined,
                    is_sender_popover: true,
                    status_text: "on the beach",
                });
                return "content-html";

            default:
                throw Error("unrecognized template: " + fn);
        }
    });

    $(".user_popover_email").each = noop;
    const image_stubber = make_image_stubber();
    window.location = {
        href: "http://chat.zulip.org/",
    };
    const base_url = window.location.href;
    handler.call(target, e);

    const avatar_img = image_stubber.get(0);
    const expected_url = new URL("avatar/42/medium?v=" + alice.avatar_version, base_url);
    assert.equal(avatar_img.src.toString(), expected_url.toString());

    // todo: load image
});

run_test("actions_popover", (override) => {
    override("popovers.hide_user_profile", noop);

    const handler = $("#main_div").get_on_handler("click", ".actions_hover");

    window.location = {
        protocol: "http:",
        host: "chat.zulip.org",
        pathname: "/",
    };

    const message = {
        id: 999,
        topic: "Actions (1)",
        type: "stream",
        stream_id: 123,
    };

    current_msg_list.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    message_edit.get_editability = () => 4;

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

    global.stub_templates((fn, opts) => {
        // TODO: Test all the properties of the popover
        switch (fn) {
            case "actions_popover_content":
                assert.equal(
                    opts.conversation_time_uri,
                    "http://chat.zulip.org/#narrow/stream/Bracket.20%28.20stream/topic/Actions.20%281%29/near/999",
                );
                return "actions-content";
            default:
                throw Error("unrecognized template: " + fn);
        }
    });

    handler.call(target, e);
});
