import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_more_topics from "../templates/more_topics.hbs";
import render_more_topics_spinner from "../templates/more_topics_spinner.hbs";
import render_topic_list_item from "../templates/topic_list_item.hbs";

import * as blueslip from "./blueslip";
import * as popover_menus from "./popover_menus";
import * as scroll_util from "./scroll_util";
import * as stream_topic_history from "./stream_topic_history";
import * as stream_topic_history_util from "./stream_topic_history_util";
import * as topic_list_data from "./topic_list_data";
import type { TopicInfo } from "./topic_list_data";
import * as vdom from "./vdom";

import { createSignal, onCleanup } from 'solid-js'; // Import Solid.js functions

const active_widgets = new Map<number, TopicListWidget>();
let zoomed = false;

export function update(): void {
    for (const widget of active_widgets.values()) {
        widget.build();
    }
}

export function clear(): void {
    popover_menus.get_topic_menu_popover()?.hide();

    for (const widget of active_widgets.values()) {
        widget.remove();
    }

    active_widgets.clear();
}

export class TopicListWidget {
    signal = createSignal({ listInfo: null, spinner: false }); // Solid.js reactive signal

    cleanupFunctions = [];

    constructor($parent_elem, my_stream_id) {
        this.$parent_elem = $parent_elem;
        this.my_stream_id = my_stream_id;
    }

    async build_list(spinner) {
        const list_info = topic_list_data.get_list_info(
            this.my_stream_id,
            zoomed,
            get_topic_search_term(),
        );

        const num_possible_topics = list_info.num_possible_topics;
        const more_topics_unreads = list_info.more_topics_unreads;
        const more_topics_have_unread_mention_messages =
            list_info.more_topics_have_unread_mention_messages;

        const is_showing_all_possible_topics =
            list_info.items.length === num_possible_topics &&
            stream_topic_history.is_complete_for_stream_id(this.my_stream_id);

        const attrs: [string, string][] = [["class", "topic-list"]];

        const nodes = list_info.items.map((conversation) => keyed_topic_li(conversation));

        if (spinner) {
            nodes.push(spinner_li());
        } else if (!is_showing_all_possible_topics) {
            nodes.push(
                more_li(
                    more_topics_unreads,
                    more_topics_have_unread_mention_messages,
                    list_info.more_topics_unread_count_muted,
                ),
            );
        }

        this.signal[0]({ listInfo: nodes, spinner }); // Update the signal with listInfo and spinner
    }

    get_parent() {
        return this.$parent_elem;
    }

    remove() {
        this.$parent_elem.find(".topic-list").remove();
        this.prior_dom = undefined;
    }

    build(spinner = false) {
        const new_dom = this.build_list(spinner);

        const replace_content = (html) => {
            this.remove();
            this.$parent_elem.append($(html));
        };

        const find = () => this.$parent_elem.find(".topic-list");

        vdom.update(replace_content, find, new_dom, this.prior_dom);

        this.prior_dom = new_dom;

        if ($("#filter-topic-input").val() !== "") {
            $("#clear_search_topic_button").show();
        } else {
            $("#clear_search_topic_button").hide();
        }
    }
}

export function clear_topic_search(e) {
    e.stopPropagation();
    const $input = $("#filter-topic-input");
    if ($input.length) {
        $input.val("");
        $input.trigger("blur");

        const stream_ids = [...active_widgets.keys()];

        const stream_id = stream_ids[0];
        const widget = active_widgets.get(stream_id);
        assert(widget !== undefined);
        const parent_widget = widget.get_parent();

        rebuild(parent_widget, stream_id);
    }
}

export function active_stream_id() {
    const stream_ids = [...active_widgets.keys()];

    if (stream_ids.length !== 1) {
        return undefined;
    }

    return stream_ids[0];
}

export function get_stream_li() {
    const widgets = [...active_widgets.values()];

    if (widgets.length !== 1) {
        return undefined;
    }

    const $stream_li = widgets[0].get_parent();
    return $stream_li;
}

export function rebuild($stream_li, stream_id) {
    const active_widget = active_widgets.get(stream_id);

    if (active_widget) {
        active_widget.build();
        return;
    }

    clear();
    const widget = new TopicListWidget($stream_li, stream_id);
    widget.build();

    active_widgets.set(stream_id, widget);
}

export function zoom_in() {
    zoomed = true;

    const stream_id = active_stream_id();
    if (stream_id === undefined) {
        blueslip.error("Cannot find widget for topic history zooming.");
        return;
    }

    const active_widget = active_widgets.get(stream_id);
    assert(active_widget !== undefined);

    function on_success() {
        if (!active_widgets.has(stream_id!)) {
            blueslip.warn("User re-narrowed before topic history was returned.");
            return;
        }

        if (!zoomed) {
            blueslip.warn("User zoomed out before topic history was returned.");
            return;
        }

        active_widget!.build();
    }

    scroll_util.get_scroll_element($("#left_sidebar_scroll_container")).scrollTop(0);

    const spinner = true;
    active_widget.build(spinner);

    stream_topic_history_util.get_server_history(stream_id, on_success);
}

export function get_topic_search_term() {
    const $filter = $<HTMLInputElement>("input#filter-topic-input");
    const filter_val = $filter.val();
    if (filter_val === undefined) {
        return "";
    }
    return filter_val.trim();
}

export function initialize({
    on_topic_click,
}) {
    $("#stream_filters").on(
        "click",
        ".sidebar-topic-check, .topic-name, .topic-markers-and-controls",
        (e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) {
                return;
            }
            if ($(e.target).closest(".show-more-topics").length > 0) {
                return;
            }

            const $stream_row = $(e.target).parents(".narrow-filter");
            const stream_id_string = $stream_row.attr("data-stream-id");
            assert(stream_id_string !== undefined);
            const stream_id = Number.parseInt(stream_id_string, 10);
            const topic = $(e.target).parents("li").attr("data-topic-name");
            on_topic_click(stream_id, topic);

            e.preventDefault();
        },
    );

    $("body").on("input", "#filter-topic-input", () => {
        const stream_id = active_stream_id();
        assert(stream_id !== undefined);
        active_widgets.get(stream_id)?.build();
    });
}
