import $ from "jquery";
import _ from "lodash";

import render_more_topics from "../templates/more_topics.hbs";
import render_more_topics_spinner from "../templates/more_topics_spinner.hbs";
import render_topic_list_item from "../templates/topic_list_item.hbs";

import * as blueslip from "./blueslip";
import * as popover_menus from "./popover_menus";
import * as scroll_util from "./scroll_util";
import * as stream_topic_history from "./stream_topic_history";
import * as stream_topic_history_util from "./stream_topic_history_util";
import * as topic_list_data from "./topic_list_data";
import * as vdom from "./vdom";

/*
    Track all active widgets with a Map.

    (We have at max one for now, but we may
    eventually allow multiple streams to be
    expanded.)
*/

const active_widgets = new Map();

// We know whether we're zoomed or not.
let zoomed = false;

export function update() {
    for (const widget of active_widgets.values()) {
        widget.build();
    }
}

export function clear() {
    popover_menus.get_topic_menu_popover()?.hide();

    for (const widget of active_widgets.values()) {
        widget.remove();
    }

    active_widgets.clear();
}

export function close() {
    zoomed = false;
    clear();
}

export function zoom_out() {
    zoomed = false;

    const stream_ids = [...active_widgets.keys()];

    if (stream_ids.length !== 1) {
        blueslip.error("Unexpected number of topic lists to zoom out.");
        return;
    }

    const stream_id = stream_ids[0];
    const widget = active_widgets.get(stream_id);
    const parent_widget = widget.get_parent();

    rebuild(parent_widget, stream_id);
}

export function keyed_topic_li(conversation) {
    const render = () => render_topic_list_item(conversation);

    const eq = (other) => _.isEqual(conversation, other.conversation);

    const key = "t:" + conversation.topic_name;

    return {
        key,
        render,
        conversation,
        eq,
    };
}

export function more_li(
    more_topics_unreads,
    more_topics_have_unread_mention_messages,
    more_topics_unread_count_muted,
) {
    const render = () =>
        render_more_topics({
            more_topics_unreads,
            more_topics_have_unread_mention_messages,
            more_topics_unread_count_muted,
        });

    const eq = (other) => other.more_items && more_topics_unreads === other.more_topics_unreads;

    const key = "more";

    return {
        key,
        more_items: true,
        more_topics_unreads,
        render,
        eq,
    };
}

export function spinner_li() {
    const render = () => render_more_topics_spinner();

    const eq = (other) => other.spinner;

    const key = "more";

    return {
        key,
        spinner: true,
        render,
        eq,
    };
}

export class TopicListWidget {
    prior_dom = undefined;

    constructor($parent_elem, my_stream_id) {
        this.$parent_elem = $parent_elem;
        this.my_stream_id = my_stream_id;
    }

    build_list(spinner) {
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

        const attrs = [["class", "topic-list"]];

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

        const dom = vdom.ul({
            attrs,
            keyed_nodes: nodes,
        });

        return dom;
    }

    get_parent() {
        return this.$parent_elem;
    }

    get_stream_id() {
        return this.my_stream_id;
    }

    remove() {
        this.$parent_elem.find(".topic-list").remove();
        this.prior_dom = undefined;
    }

    build(spinner) {
        const new_dom = this.build_list(spinner);

        const replace_content = (html) => {
            this.remove();
            this.$parent_elem.append(html);
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

        // Since this changes the contents of the search input, we
        // need to rerender the topic list.
        const stream_ids = [...active_widgets.keys()];

        const stream_id = stream_ids[0];
        const widget = active_widgets.get(stream_id);
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

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
export function zoom_in() {
    zoomed = true;

    const stream_id = active_stream_id();
    if (!stream_id) {
        blueslip.error("Cannot find widget for topic history zooming.");
        return;
    }

    const active_widget = active_widgets.get(stream_id);

    function on_success() {
        if (!active_widgets.has(stream_id)) {
            blueslip.warn("User re-narrowed before topic history was returned.");
            return;
        }

        if (!zoomed) {
            blueslip.warn("User zoomed out before topic history was returned.");
            // Note that we could attempt to re-draw the zoomed out topic list
            // here, given that we have more history, but that might be more
            // confusing than helpful to a user who is likely trying to browse
            // other streams.
            return;
        }

        active_widget.build();
    }

    scroll_util.get_scroll_element($("#left_sidebar_scroll_container")).scrollTop(0);

    const spinner = true;
    active_widget.build(spinner);

    stream_topic_history_util.get_server_history(stream_id, on_success);
}

export function get_topic_search_term() {
    const $filter = $("#filter-topic-input");
    if ($filter.val() === undefined) {
        return "";
    }
    return $filter.val().trim();
}

export function initialize({on_topic_click}) {
    $("#stream_filters").on("click", ".topic-box", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if ($(e.target).closest(".show-more-topics").length > 0) {
            return;
        }

        const $stream_row = $(e.target).parents(".narrow-filter");
        const stream_id = Number.parseInt($stream_row.attr("data-stream-id"), 10);
        const topic = $(e.target).parents("li").attr("data-topic-name");
        on_topic_click(stream_id, topic);

        e.preventDefault();
    });

    $("body").on("input", "#filter-topic-input", () => {
        active_widgets.get(active_stream_id()).build();
    });
}
