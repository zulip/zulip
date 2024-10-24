import type {z} from "zod";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import {FoldDict} from "./fold_dict";
import * as loading from "./loading";
import * as settings_ui from "./settings_ui";
import type {StateData, topic_settings_schema} from "./state_data";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";
import {get_time_from_date_muted} from "./util";

export type SeverTopicSettings = z.infer<typeof topic_settings_schema>;

export type TopiSetting = {
    stream_id: number;
    stream: string;
    topic: string;
    date_updated: number;
    date_updated_str: string;
    is_locked: boolean;
};

const all_topic_settings = new Map<
    number,
    FoldDict<{
        stream_name: string;
        date_updated: number;
        is_locked: boolean;
    }>
>();

export function update_topic_settings(
    stream_id: number,
    stream_name: string,
    topic: string,
    is_locked: boolean,
    date_updated: number,
): void {
    let sub_dict = all_topic_settings.get(stream_id);
    if (!sub_dict) {
        sub_dict = new FoldDict();
        all_topic_settings.set(stream_id, sub_dict);
    }
    const time = get_time_from_date_muted(date_updated);
    sub_dict.set(topic, {date_updated: time, is_locked, stream_name});
}

export function get_topic_lock_status(stream_id: number, topic: string): boolean {
    if (stream_id === undefined) {
        return false;
    }
    const sub_dict = all_topic_settings.get(stream_id);
    return sub_dict?.get(topic)?.is_locked ?? false;
}

export function set_topic_setting_lock_status(
    stream_id: number,
    topic: string,
    is_locked: boolean,
    $status_element?: JQuery,
    success_cb?: () => void,
    error_cb?: () => void,
): void {
    const data = {
        stream_id,
        topic,
        is_locked,
    };

    let $spinner: JQuery;

    if ($status_element) {
        $spinner = $status_element.expectOne();
        $spinner.fadeTo(0, 1);
        loading.make_indicator($spinner, {text: settings_ui.strings.saving});
    }
    void channel.post({
        url: "/json/topic_settings",
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
        },
        error() {
            if (error_cb) {
                error_cb();
            }
        },
    });
}

export function set_topic_setting(topic_setting: SeverTopicSettings): void {
    const stream_id = topic_setting.stream_id;
    const topic = topic_setting.topic_name;
    const date_updated = topic_setting.last_updated;
    const stream_name = sub_store.maybe_get_stream_name(stream_id);

    if (!stream_name) {
        blueslip.warn("Unknown channel ID in set_topic_setting: " + stream_id);
        return;
    }

    update_topic_settings(stream_id, stream_name, topic, topic_setting.is_locked, date_updated);
}

export function set_topic_settings(topic_settings: SeverTopicSettings[]): void {
    all_topic_settings.clear();
    for (const topic_setting of topic_settings) {
        set_topic_setting(topic_setting);
    }
}

export function initialize(params: StateData["topic_settings"]): void {
    set_topic_settings(params.topic_settings);
}
