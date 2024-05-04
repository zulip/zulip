import $ from "jquery";
import assert from "minimalistic-assert";

import render_user_topic_ui_row from "../templates/user_topic_ui_row.hbs";

import * as ListWidget from "./list_widget";
import * as scroll_util from "./scroll_util";
import * as settings_config from "./settings_config";
import * as user_topics from "./user_topics";
import type {UserTopic} from "./user_topics";

export let loaded = false;

export function populate_list(): void {
    const all_user_topics = [];
    const visibility_policies = Object.values(user_topics.all_visibility_policies);
    for (const visibility_policy of visibility_policies) {
        /* For visibility_policy=INHERIT, 'get_user_topics_for_visibility_policy' returns
        an empty list as we only maintain the record of topics having visibility_policy
        other than INHERIT; INHERIT is used to remove topics from the record. */
        const user_topics_list =
            user_topics.get_user_topics_for_visibility_policy(visibility_policy);
        all_user_topics.push(...user_topics_list);
    }
    const $user_topics_table = $("#user_topics_table");
    const $search_input = $<HTMLInputElement>("#user_topics_search");

    ListWidget.create<UserTopic>($user_topics_table, all_user_topics, {
        name: "user-topics-list",
        get_item: ListWidget.default_get_item,
        modifier_html(user_topic) {
            const context = {
                user_topic,
                user_topic_visibility_policy_values:
                    settings_config.user_topic_visibility_policy_values,
            };
            return render_user_topic_ui_row(context);
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.topic.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                scroll_util.reset_scrollbar(
                    $user_topics_table.closest(".progressive-table-wrapper"),
                );
            },
        },
        init_sort: "date_updated_numeric",
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["stream", "topic"]),
            ...ListWidget.generic_sort_functions("numeric", ["date_updated", "visibility_policy"]),
        },
        initially_descending_sort: true,
        $parent_container: $("#user-topic-settings"),
        $simplebar_container: $("#user-topic-settings .progressive-table-wrapper"),
    });
}

export function set_up(): void {
    loaded = true;

    $("body").on(
        "change",
        "select.settings_user_topic_visibility_policy",
        function (this: HTMLSelectElement, e) {
            const $row = $(this).closest("tr");
            const stream_id_string = $row.attr("data-stream-id");
            assert(stream_id_string !== undefined);
            const stream_id = Number.parseInt(stream_id_string, 10);
            const topic = $row.attr("data-topic");
            assert(topic !== undefined);
            const visibility_policy = Number(this.value);

            e.stopPropagation();

            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                visibility_policy,
                false,
                false,
                $row.closest("#user-topic-settings").find(".alert-notification"),
            );
        },
    );

    populate_list();
}

export function reset(): void {
    loaded = false;
}
