import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_more_topics from "../templates/more_topics.hbs";
import render_more_topics_spinner from "../templates/more_topics_spinner.hbs";
import render_topic_list_item from "../templates/topic_list_item.hbs";

import {all_messages_data} from "./all_messages_data.ts";
import * as blueslip from "./blueslip.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as scroll_util from "./scroll_util.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as sub_store from "./sub_store.ts";
import * as topic_list_data from "./topic_list_data.ts";
import type {TopicInfo} from "./topic_list_data.ts";
import * as vdom from "./vdom.ts";

/*
    Track all active widgets with a Map by stream_id.

    (We have at max one for now, but we may
    eventually allow multiple streams to be
    expanded.)
*/

const active_widgets = new Map<number, LeftSidebarTopicListWidget>();

// We know whether we're zoomed or not.
let zoomed = false;

export function update(): void {
    for (const widget of active_widgets.values()) {
        widget.build();
    }
}

function update_widget_for_stream(stream_id: number): void {
    const widget = active_widgets.get(stream_id);
    if (widget === undefined) {
        blueslip.warn("User re-narrowed before topic history was returned.");
        return;
    }
    widget.build();
}

export function clear(): void {
    popover_menus.get_topic_menu_popover()?.hide();

    for (const widget of active_widgets.values()) {
        widget.remove();
    }

    active_widgets.clear();
}

export function focus_topic_search_filter(): void {
    popovers.hide_all();
    sidebar_ui.show_left_sidebar();
    const $filter = $("#left-sidebar-filter-topic-input").expectOne();
    $filter.trigger("focus");
}

export function close(): void {
    zoomed = false;
    clear();
}

export function zoom_out(): void {
    zoomed = false;

    const stream_ids = [...active_widgets.keys()];

    if (stream_ids.length !== 1 || stream_ids[0] === undefined) {
        blueslip.error("Unexpected number of topic lists to zoom out.");
        return;
    }

    const stream_id = stream_ids[0];
    const widget = active_widgets.get(stream_id);
    assert(widget !== undefined);
    const parent_widget = widget.get_parent();

    rebuild_left_sidebar(parent_widget, stream_id);
}

type ListInfoNodeOptions =
    | {
          type: "topic";
          conversation: TopicInfo;
      }
    | {
          type: "more_items";
          more_topics_unreads: number;
      }
    | {
          type: "spinner";
      };

type ListInfoNode = vdom.Node<ListInfoNodeOptions>;

export function keyed_topic_li(conversation: TopicInfo): ListInfoNode {
    const render = (): string => render_topic_list_item(conversation);

    const eq = (other: ListInfoNode): boolean =>
        other.type === "topic" && _.isEqual(conversation, other.conversation);

    const key = "t:" + conversation.topic_name;

    return {
        key,
        render,
        type: "topic",
        conversation,
        eq,
    };
}

export function more_li(
    more_topics_unreads: number,
    more_topics_have_unread_mention_messages: boolean,
    more_topics_unread_count_muted: boolean,
): ListInfoNode {
    const render = (): string =>
        render_more_topics({
            more_topics_unreads,
            more_topics_have_unread_mention_messages,
            more_topics_unread_count_muted,
        });

    const eq = (other: ListInfoNode): boolean =>
        other.type === "more_items" && more_topics_unreads === other.more_topics_unreads;

    const key = "more";

    return {
        key,
        type: "more_items",
        more_topics_unreads,
        render,
        eq,
    };
}

export function spinner_li(): ListInfoNode {
    const render = (): string => render_more_topics_spinner();

    const eq = (other: ListInfoNode): boolean => other.type === "spinner";

    const key = "more";

    return {
        key,
        type: "spinner",
        render,
        eq,
    };
}

export function is_full_topic_history_available(
    stream_id: number,
    num_topics_displayed: number,
): boolean {
    if (stream_topic_history.has_history_for(stream_id)) {
        return true;
    }

    function all_topics_in_cache(sub: StreamSubscription): boolean {
        // Checks whether this browser's cache of contiguous messages
        // (used to locally render narrows) in all_messages_data has all
        // messages from a given stream. Because all_messages_data is a range,
        // we just need to compare it to the range of history on the stream.

        // If the cache isn't initialized, it's a clear false.
        if (all_messages_data === undefined || all_messages_data.empty()) {
            return false;
        }

        // If the cache doesn't have the latest messages, we can't be sure
        // we have all topics.
        if (!all_messages_data.fetch_status.has_found_newest()) {
            return false;
        }

        if (sub.first_message_id === null) {
            // If the stream has no message history, we have it all
            // vacuously.  This should be a very rare condition, since
            // stream creation sends a message.
            return true;
        }

        const first_cached_message = all_messages_data.first_including_muted();
        if (sub.first_message_id < first_cached_message!.id) {
            // Missing the oldest topics in this stream in our cache.
            return false;
        }

        // At this stage, number of topics displayed in the topic list
        // widget is at max `topic_list_data.max_topics` and
        // sub.first_message_id >= first_cached_message!.id.
        //
        // There's a possibility of a few topics missing for messages
        // which were sent when the user wasn't subscribed.
        // Fetch stream history to confirm if all topics are already
        // displayed otherwise rebuild with updated data.
        stream_topic_history_util.get_server_history(stream_id, () => {
            const history = stream_topic_history.find_or_create(stream_id);
            if (history.topics.size > num_topics_displayed) {
                update_widget_for_stream(stream_id);
            }
        });
        // We return `false` which leads to visible 'show all topics',
        // even if all the topics are already displayed.
        // This is helpful if the API call fails, users will have
        // the option to make another request. Otherwise there's
        // a possibility of missing 'show all topics' & not all topics displayed.
        return false;
    }

    const sub = sub_store.get(stream_id);
    const in_cache = sub !== undefined && all_topics_in_cache(sub);

    if (in_cache) {
        /*
            If the stream is cached, we can add it to
            fetched_stream_ids.  Note that for the opposite
            scenario, we don't delete from
            fetched_stream_ids, because we may just be
            waiting for the initial message fetch.
        */
        stream_topic_history.mark_history_fetched_for(stream_id);
    }

    return in_cache;
}

export class TopicListWidget {
    prior_dom: vdom.Tag<ListInfoNodeOptions> | undefined = undefined;
    $parent_elem: JQuery;
    my_stream_id: number;
    filter_topics: (topic_names: string[]) => string[];

    constructor(
        $parent_elem: JQuery,
        my_stream_id: number,
        filter_topics: (topic_names: string[]) => string[],
    ) {
        this.$parent_elem = $parent_elem;
        this.my_stream_id = my_stream_id;
        this.filter_topics = filter_topics;
    }

    build_list(
        spinner: boolean,
        formatter: (conversation: TopicInfo) => ListInfoNode,
        is_zoomed: boolean,
    ): vdom.Tag<ListInfoNodeOptions> {
        const list_info = topic_list_data.get_list_info(
            this.my_stream_id,
            is_zoomed,
            this.filter_topics,
        );

        const num_possible_topics = list_info.num_possible_topics;
        const more_topics_unreads = list_info.more_topics_unreads;
        const more_topics_have_unread_mention_messages =
            list_info.more_topics_have_unread_mention_messages;

        const is_showing_all_possible_topics =
            list_info.items.length === num_possible_topics &&
            is_full_topic_history_available(this.my_stream_id, num_possible_topics);

        const topic_list_classes: [string] = ["topic-list"];

        if (list_info.items.length > 0) {
            topic_list_classes.push("topic-list-has-topics");
        }

        const attrs: [string, string][] = [["class", topic_list_classes.join(" ")]];

        const nodes = list_info.items.map((conversation) => formatter(conversation));

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

    get_parent(): JQuery {
        return this.$parent_elem;
    }

    get_stream_id(): number {
        return this.my_stream_id;
    }

    remove(): void {
        this.$parent_elem.find(".topic-list").remove();
        this.prior_dom = undefined;
    }

    build(
        spinner = false,
        formatter: (conversation: TopicInfo) => ListInfoNode,
        is_zoomed: boolean,
    ): void {
        const new_dom = this.build_list(spinner, formatter, is_zoomed);

        const replace_content = (html: string): void => {
            this.remove();
            this.$parent_elem.append($(html));
        };

        const find = (): JQuery => this.$parent_elem.find(".topic-list");

        vdom.update(replace_content, find, new_dom, this.prior_dom);

        this.prior_dom = new_dom;
    }

    is_empty(): boolean {
        const $topic_list = this.$parent_elem.find(".topic-list");
        return !$topic_list.hasClass("topic-list-has-topics");
    }
}

function filter_topics_left_sidebar(topic_names: string[]): string[] {
    const search_term = get_left_sidebar_topic_search_term();
    return topic_list_data.filter_topics_by_search_term(topic_names, search_term);
}

export class LeftSidebarTopicListWidget extends TopicListWidget {
    constructor($parent_elem: JQuery, my_stream_id: number) {
        super($parent_elem, my_stream_id, filter_topics_left_sidebar);
    }

    override build(spinner = false): void {
        const is_zoomed = zoomed;
        const formatter = keyed_topic_li;

        super.build(spinner, formatter, is_zoomed);
    }
}

export function clear_topic_search(e: JQuery.Event): void {
    e.stopPropagation();
    const $input = $("#left-sidebar-filter-topic-input");
    if ($input.length > 0) {
        $input.val("");
        $input.trigger("blur");

        // Since this changes the contents of the search input, we
        // need to rerender the topic list.
        const stream_ids = [...active_widgets.keys()];

        const stream_id = stream_ids[0];
        assert(stream_id !== undefined);
        const widget = active_widgets.get(stream_id);
        assert(widget !== undefined);
        const parent_widget = widget.get_parent();

        rebuild_left_sidebar(parent_widget, stream_id);
    }
}

export function active_stream_id(): number | undefined {
    const stream_ids = [...active_widgets.keys()];

    if (stream_ids.length !== 1) {
        return undefined;
    }

    return stream_ids[0];
}

export function get_stream_li(): JQuery | undefined {
    const widgets = [...active_widgets.values()];

    if (widgets.length !== 1 || widgets[0] === undefined) {
        return undefined;
    }

    const $stream_li = widgets[0].get_parent();
    return $stream_li;
}

export function rebuild_left_sidebar($stream_li: JQuery, stream_id: number): void {
    const active_widget = active_widgets.get(stream_id);

    if (active_widget) {
        active_widget.build();
        return;
    }

    clear();
    const widget = new LeftSidebarTopicListWidget($stream_li, stream_id);
    widget.build();

    active_widgets.set(stream_id, widget);
}

export function scroll_zoomed_in_topic_into_view(): void {
    const $selected_topic = $(".topic-list .topic-list-item.active-sub-filter");
    if ($selected_topic.length === 0) {
        // If we don't have a selected topic, scroll to top.
        scroll_util.get_scroll_element($("#left_sidebar_scroll_container")).scrollTop(0);
        return;
    }
    const $container = $("#left_sidebar_scroll_container");
    const stream_header_height =
        $(".narrow-filter.stream-expanded .bottom_left_row").outerHeight(true) ?? 0;
    const topic_header_height = $("#topics_header").outerHeight(true) ?? 0;
    const sticky_header_height = stream_header_height + topic_header_height;
    scroll_util.scroll_element_into_container($selected_topic, $container, sticky_header_height);
}

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
export function zoom_in(): void {
    zoomed = true;

    const stream_id = active_stream_id();
    if (stream_id === undefined) {
        blueslip.error("Cannot find widget for topic history zooming.");
        return;
    }

    const active_widget = active_widgets.get(stream_id);
    assert(active_widget !== undefined);

    function on_success(): void {
        if (!active_widgets.has(stream_id!)) {
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

        active_widget!.build();
        if (zoomed) {
            // It is fine to force scroll here even if user has scrolled to a different
            // position since we just added some topics to the list which moved user
            // to a different position anyway.
            scroll_zoomed_in_topic_into_view();
        }
    }

    const spinner = true;
    active_widget.build(spinner);

    stream_topic_history_util.get_server_history(stream_id, on_success);
    scroll_zoomed_in_topic_into_view();
}

export function get_left_sidebar_topic_search_term(): string {
    const $filter = $<HTMLInputElement>("input#left-sidebar-filter-topic-input");
    const filter_val = $filter.val();
    if (filter_val === undefined) {
        return "";
    }
    return filter_val.trim();
}

export function initialize({
    on_topic_click,
}: {
    on_topic_click: (stream_id: number, topic?: string) => void;
}): void {
    $("#stream_filters").on(
        "click",
        ".sidebar-topic-check, .sidebar-topic-name, .topic-markers-and-unreads",
        (e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) {
                return;
            }
            if ($(e.target).closest(".show-more-topics").length > 0) {
                return;
            }

            if ($(e.target).hasClass("visibility-policy-icon")) {
                return;
            }

            const $stream_row = $(e.target).parents(".narrow-filter");
            const stream_id_string = $stream_row.attr("data-stream-id");
            assert(stream_id_string !== undefined);
            const stream_id = Number.parseInt(stream_id_string, 10);
            const topic = $(e.target).parents("li").attr("data-topic-name");
            on_topic_click(stream_id, topic);

            e.preventDefault();
            e.stopPropagation();
        },
    );

    $("body").on("input", "#left-sidebar-filter-topic-input", (): void => {
        const stream_id = active_stream_id();
        assert(stream_id !== undefined);
        active_widgets.get(stream_id)?.build();
    });
}
