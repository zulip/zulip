import type * as z from "zod/mini";

import render_topic_muted from "../templates/topic_muted.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_banner from "./compose_banner.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {FoldDict} from "./fold_dict.ts";
import {$t} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as settings_ui from "./settings_ui.ts";
import type {StateData, user_topic_schema} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import {get_time_from_date_muted} from "./util.ts";

export type ServerUserTopic = z.infer<typeof user_topic_schema>;

export type UserTopic = {
    stream_id: number;
    stream: string;
    topic: string;
    date_updated: number;
    date_updated_str: string;
    visibility_policy: number;
};

const all_user_topics = new Map<
    number,
    FoldDict<{
        stream_name: string;
        date_updated: number;
        visibility_policy: number;
    }>
>();

export type AllVisibilityPolicies = {
    INHERIT: 0;
    MUTED: 1;
    UNMUTED: 2;
    FOLLOWED: 3;
};

export const all_visibility_policies = {
    INHERIT: 0,
    MUTED: 1,
    UNMUTED: 2,
    FOLLOWED: 3,
} as const;

export function update_user_topics(
    stream_id: number,
    stream_name: string,
    topic: string,
    visibility_policy: number,
    date_updated: number,
): void {
    let sub_dict = all_user_topics.get(stream_id);
    if (visibility_policy === all_visibility_policies.INHERIT && sub_dict) {
        sub_dict.delete(topic);
    } else {
        if (!sub_dict) {
            sub_dict = new FoldDict();
            all_user_topics.set(stream_id, sub_dict);
        }
        const time = get_time_from_date_muted(date_updated);
        sub_dict.set(topic, {date_updated: time, visibility_policy, stream_name});
    }
}

export function get_topic_visibility_policy(stream_id: number, topic: string): number | false {
    if (stream_id === undefined) {
        return false;
    }
    const sub_dict = all_user_topics.get(stream_id);
    return sub_dict?.get(topic)?.visibility_policy ?? all_visibility_policies.INHERIT;
}

export function is_topic_followed(stream_id: number, topic: string): boolean {
    return get_topic_visibility_policy(stream_id, topic) === all_visibility_policies.FOLLOWED;
}

export function is_topic_unmuted(stream_id: number, topic: string): boolean {
    return get_topic_visibility_policy(stream_id, topic) === all_visibility_policies.UNMUTED;
}

export function is_topic_muted(stream_id: number, topic: string): boolean {
    return get_topic_visibility_policy(stream_id, topic) === all_visibility_policies.MUTED;
}

export function is_topic_unmuted_or_followed(stream_id: number, topic: string): boolean {
    return is_topic_unmuted(stream_id, topic) || is_topic_followed(stream_id, topic);
}

export function get_user_topics_for_visibility_policy(visibility_policy: number): UserTopic[] {
    const topics: UserTopic[] = [];
    for (const [stream_id, sub_dict] of all_user_topics) {
        for (const topic of sub_dict.keys()) {
            if (sub_dict.get(topic)!.visibility_policy === visibility_policy) {
                const topic_dict = sub_dict.get(topic)!;
                const date_updated = topic_dict.date_updated;
                const date_updated_str = timerender.render_now(new Date(date_updated)).time_str;
                topics.push({
                    stream_id,
                    stream: topic_dict.stream_name,
                    topic,
                    date_updated,
                    date_updated_str,
                    visibility_policy,
                });
            }
        }
    }
    return topics;
}

export let set_user_topic_visibility_policy = (
    stream_id: number,
    topic: string,
    visibility_policy: number,
    from_hotkey?: boolean,
    from_banner?: boolean,
    $status_element?: JQuery,
    success_cb?: () => void,
    error_cb?: () => void,
): void => {
    const data = {
        stream_id,
        topic,
        visibility_policy,
    };

    let $spinner: JQuery;
    if ($status_element) {
        $spinner = $status_element.expectOne();
        $spinner.fadeTo(0, 1);
        loading.make_indicator($spinner, {text: settings_ui.strings.saving});
    }

    void channel.post({
        url: "/json/user_topics",
        data,
        success() {
            if (success_cb) {
                success_cb();
            }

            if ($status_element) {
                const remove_after = 1000;
                const appear_after = 500;
                setTimeout(() => {
                    ui_report.success(settings_ui.strings.success_html, $spinner, remove_after);
                    settings_ui.display_checkmark($spinner);
                }, appear_after);
                return;
            }

            if (visibility_policy === all_visibility_policies.INHERIT) {
                feedback_widget.dismiss();
                return;
            }
            if (from_banner) {
                compose_banner.clear_unmute_topic_notifications();
                return;
            }
            if (!from_hotkey) {
                return;
            }

            // The following feedback_widget notice helps avoid
            // confusion when a user who is not familiar with Zulip's
            // keyboard UI hits "M" in the wrong context and has a
            // bunch of messages suddenly disappear. This notice is
            // only useful when muting from the keyboard, since you
            // know what you did if you triggered muting with the
            // mouse.
            if (visibility_policy === all_visibility_policies.MUTED) {
                const stream_name = sub_store.maybe_get_stream_name(stream_id);
                feedback_widget.show({
                    populate($container) {
                        const rendered_html = render_topic_muted({});
                        $container.html(rendered_html);
                        $container.find(".stream").text(stream_name ?? "");
                        $container.find(".topic").text(topic);
                    },
                    on_undo() {
                        set_user_topic_visibility_policy(
                            stream_id,
                            topic,
                            all_visibility_policies.INHERIT,
                        );
                    },
                    title_text: $t({defaultMessage: "Topic muted"}),
                    undo_button_text: $t({defaultMessage: "Undo mute"}),
                });
            }
        },
        error() {
            if (error_cb) {
                error_cb();
            }
        },
    });
};

export function rewire_set_user_topic_visibility_policy(
    value: typeof set_user_topic_visibility_policy,
): void {
    set_user_topic_visibility_policy = value;
}

export function set_visibility_policy_for_element($elt: JQuery, visibility_policy: number): void {
    const stream_id = Number.parseInt($elt.attr("data-stream-id")!, 10);
    const topic = $elt.attr("data-topic-name")!;
    set_user_topic_visibility_policy(stream_id, topic, visibility_policy);
}

export function set_user_topic(user_topic: ServerUserTopic): void {
    const stream_id = user_topic.stream_id;
    const topic = user_topic.topic_name;
    const date_updated = user_topic.last_updated;

    const stream_name = sub_store.maybe_get_stream_name(stream_id);

    if (!stream_name) {
        blueslip.warn("Unknown stream ID in set_user_topic: " + stream_id);
        return;
    }

    update_user_topics(stream_id, stream_name, topic, user_topic.visibility_policy, date_updated);
}

export function set_user_topics(user_topics: ServerUserTopic[]): void {
    all_user_topics.clear();

    for (const user_topic of user_topics) {
        set_user_topic(user_topic);
    }
}

export function is_topic_visible_in_home(stream_id: number, topic: string): boolean {
    // This determines if topic will be visible in combined feed just based
    // on topic visibility policy and stream properties.
    if (is_topic_muted(stream_id, topic)) {
        // If topic is muted, we don't show the message.
        return false;
    }

    return (
        // If channel is muted, we show the message if topic is unmuted or followed.
        !stream_data.is_muted(stream_id) || is_topic_unmuted_or_followed(stream_id, topic)
    );
}

export function initialize(params: StateData["user_topics"]): void {
    set_user_topics(params.user_topics);
}
