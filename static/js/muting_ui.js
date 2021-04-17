import $ from "jquery";

import render_confirm_mute_user from "../templates/confirm_mute_user.hbs";
import render_muted_topic_ui_row from "../templates/muted_topic_ui_row.hbs";
import render_topic_muted from "../templates/topic_muted.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as feedback_widget from "./feedback_widget";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as message_lists from "./message_lists";
import * as muting from "./muting";
import * as overlays from "./overlays";
import * as people from "./people";
import * as popovers from "./popovers";
import * as recent_topics from "./recent_topics";
import * as settings_muted_topics from "./settings_muted_topics";
import * as settings_muted_users from "./settings_muted_users";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_popover from "./stream_popover";
import * as ui from "./ui";
import * as unread_ui from "./unread_ui";

function timestamp_ms() {
    return Date.now();
}

let last_topic_update = 0;

export function rerender_on_topic_update() {
    // Note: We tend to optimistically rerender muting preferences before
    // the backend actually acknowledges the mute.  This gives a more
    // immediate feel to the user, and if the backend fails temporarily,
    // re-doing a mute or unmute is a pretty recoverable thing.

    stream_list.update_streams_sidebar();
    recent_topics.complete_rerender();
    message_lists.current.update_topic_muting_and_rerender();
    if (message_lists.current !== message_lists.home) {
        message_lists.home.update_topic_muting_and_rerender();
    }
    if (overlays.settings_open() && settings_muted_topics.loaded) {
        set_up_muted_topics_ui();
    }
}

export function persist_topic_mute(stream_id, topic_name) {
    const data = {
        stream_id,
        topic: topic_name,
        op: "add",
    };
    last_topic_update = timestamp_ms();
    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
    });
}

export function persist_topic_unmute(stream_id, topic_name) {
    const data = {
        stream_id,
        topic: topic_name,
        op: "remove",
    };
    last_topic_update = timestamp_ms();
    channel.patch({
        url: "/json/users/me/subscriptions/muted_topics",
        idempotent: true,
        data,
    });
}

export function handle_topic_updates(muted_topics) {
    if (timestamp_ms() < last_topic_update + 1000) {
        // This topic update is either the one that we just rendered, or,
        // much less likely, it's coming from another device and would probably
        // be overwriting this device's preferences with stale data.
        return;
    }

    update_muted_topics(muted_topics);
    rerender_on_topic_update();
}

export function update_muted_topics(muted_topics) {
    muting.set_muted_topics(muted_topics);
    unread_ui.update_unread_counts();
}

export function set_up_muted_topics_ui() {
    const muted_topics = muting.get_muted_topics();
    const muted_topics_table = $("#muted_topics_table");
    const $search_input = $("#muted_topics_search");

    ListWidget.create(muted_topics_table, muted_topics, {
        name: "muted-topics-list",
        modifier(muted_topics) {
            return render_muted_topic_ui_row({muted_topics});
        },
        filter: {
            element: $search_input,
            predicate(item, value) {
                return item.topic.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar(muted_topics_table.closest(".progressive-table-wrapper"));
            },
        },
        parent_container: $("#muted-topic-settings"),
        simplebar_container: $("#muted-topic-settings .progressive-table-wrapper"),
    });
}

export function mute_topic(stream_id, topic) {
    const stream_name = stream_data.maybe_get_stream_name(stream_id);

    stream_popover.hide_topic_popover();
    muting.add_muted_topic(stream_id, topic);
    unread_ui.update_unread_counts();
    rerender_on_topic_update();
    persist_topic_mute(stream_id, topic);
    feedback_widget.show({
        populate(container) {
            const rendered_html = render_topic_muted();
            container.html(rendered_html);
            container.find(".stream").text(stream_name);
            container.find(".topic").text(topic);
        },
        on_undo() {
            unmute_topic(stream_id, topic);
        },
        title_text: $t({defaultMessage: "Topic muted"}),
        undo_button_text: $t({defaultMessage: "Unmute"}),
    });
    recent_topics.update_topic_is_muted(stream_id, topic);
}

export function unmute_topic(stream_id, topic) {
    // we don't run a unmute_notify function because it isn't an issue as much
    // if someone accidentally unmutes a stream rather than if they mute it
    // and miss out on info.
    stream_popover.hide_topic_popover();
    muting.remove_muted_topic(stream_id, topic);
    unread_ui.update_unread_counts();
    rerender_on_topic_update();
    persist_topic_unmute(stream_id, topic);
    feedback_widget.dismiss();
    recent_topics.update_topic_is_muted(stream_id, topic);
}

export function toggle_topic_mute(message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    if (muting.is_topic_muted(stream_id, topic)) {
        unmute_topic(stream_id, topic);
    } else if (message.type === "stream") {
        mute_topic(stream_id, topic);
    }
}

export function mute_user(user_id) {
    channel.post({
        url: "/json/users/me/muted_users/" + user_id,
        idempotent: true,
    });
}

export function confirm_mute_user(user_id) {
    function on_click() {
        mute_user(user_id);
    }

    const modal_parent = $(".mute-user-modal-holder");
    const html_body = render_confirm_mute_user({
        user_name: people.get_full_name(user_id),
    });

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: $t({defaultMessage: "Mute user"}),
        html_body,
        html_yes_button: $t({defaultMessage: "Confirm"}),
        on_click,
    });
}

export function unmute_user(user_id) {
    channel.del({
        url: "/json/users/me/muted_users/" + user_id,
        idempotent: true,
    });
}

export function rerender_for_muted_user() {
    if (overlays.settings_open() && settings_muted_users.loaded) {
        settings_muted_users.populate_list();
    }
}

export function handle_user_updates(muted_user_ids) {
    popovers.hide_all();
    muting.set_muted_users(muted_user_ids);
    rerender_for_muted_user();
}
