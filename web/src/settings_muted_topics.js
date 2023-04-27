import $ from "jquery";

import render_user_topic_ui_row from "../templates/user_topic_ui_row.hbs";

import * as ListWidget from "./list_widget";
import * as ui from "./ui";
import * as user_topics from "./user_topics";

export let loaded = false;

export function populate_list() {
    const all_muted_topics = user_topics.get_user_topics_for_visibility_policy(
        user_topics.all_visibility_policies.MUTED,
    );
    const $muted_topics_table = $("#muted_topics_table");
    const $search_input = $("#muted_topics_search");

    ListWidget.create($muted_topics_table, all_muted_topics, {
        name: "muted-topics-list",
        modifier(user_topic) {
            return render_user_topic_ui_row({user_topic});
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.topic.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar($muted_topics_table.closest(".progressive-table-wrapper"));
            },
        },
        $parent_container: $("#muted-topic-settings"),
        $simplebar_container: $("#muted-topic-settings .progressive-table-wrapper"),
    });
}

export function set_up() {
    loaded = true;
    $("body").on("click", ".settings-unmute-topic", function (e) {
        const $row = $(this).closest("tr");
        const stream_id = Number.parseInt($row.attr("data-stream-id"), 10);
        const topic = $row.attr("data-topic");

        e.stopPropagation();

        user_topics.set_user_topic_visibility_policy(
            stream_id,
            topic,
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    populate_list();
}

export function reset() {
    loaded = false;
}
