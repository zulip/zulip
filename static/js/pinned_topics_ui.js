import _ from "lodash";

import render_topic_muted from "../templates/topic_muted.hbs";

import * as channel from "./channel";
import * as feedback_widget from "./feedback_widget";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as overlays from "./overlays";
import * as recent_topics_ui from "./recent_topics_ui";
import * as settings_muted_topics from "./settings_muted_topics";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_popover from "./stream_popover";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";

export function pin_topic(stream_id, topic, from_hotkey) {
    const stream_name = stream_data.maybe_get_stream_name(stream_id);
    // fomatting ref: bulk_set_stream_property in stream_edit.js, which calls 
    // update_subscription_properties_backend that has similar interface
    const raw_data = [{
        stream_id:stream_id,
        topic:topic,
        property:"is_pinned",
        value: true,
    }];
    const data = {subscription_data: JSON.stringify(raw_data)};

    channel.patch({
        url: "/json/users/me/subscriptions/pinned_topics",
        data,
        success() {
            if (!from_hotkey) {
                return;
            }

            // The following feedback_widget notice helps avoid
            // confusion when a user who is not familiar with Zulip's
            // keyboard UI hits "M" in the wrong context and has a
            // bunch of messages suddenly disappear.  This notice is
            // only useful when muting from the keyboard, since you
            // know what you did if you triggered muting with the
            // mouse.

            // @Note: simplified
            feedback_widget.show({
                // populate($container) {
                //     const rendered_html = render_topic_muted();
                //     $container.html(rendered_html);
                //     $container.find(".stream").text(stream_name);
                //     $container.find(".topic").text(topic);
                // },
                // on_undo() {
                //     unmute_topic(stream_id, topic);
                // },
                title_text: $t({defaultMessage: "Topic pinned"}),
                // undo_button_text: $t({defaultMessage: "Unmute"}),
            });
        },
    });
}

export function unpin_topic(stream_id, topic) {
    // Accidentally unmuting a topic isn't as much an issue as accidentally muting
    // a topic, so we don't show a popup after unmuting.
    const raw_data = [{
        stream_id:stream_id,
        topic:topic,
        property:"is_pinned",
        value: false,
    }];
    const data = {subscription_data: JSON.stringify(raw_data)};

    channel.patch({
        url: "/json/users/me/subscriptions/pinned_topics",
        data,
        success() {
            feedback_widget.dismiss();
        },
    });
}