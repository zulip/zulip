import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_more_topics from "../templates/more_topics.hbs";
import render_more_topics_spinner from "../templates/more_topics_spinner.hbs";
import render_topic_list_item from "../templates/topic_list_item.hbs";

import {all_messages_data} from "./all_messages_data.ts";
import * as blueslip from "./blueslip.ts";
import {Typeahead} from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import {$t} from "./i18n.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as scroll_util from "./scroll_util.ts";
import type {SearchPillWidget} from "./search_pill.ts";
import * as search_pill from "./search_pill.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as sub_store from "./sub_store.ts";
import * as topic_list_data from "./topic_list_data.ts";
import type {TopicInfo} from "./topic_list_data.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as vdom from "./vdom.ts";

type TopicFilterPill = {
    label: string;
    syntax: string;
};

const filter_options: TopicFilterPill[] = [
    {
        label: $t({defaultMessage: "Unresolved topics"}),
        syntax: "-is:resolved",
    },
    {
        label: $t({defaultMessage: "Resolved topics"}),
        syntax: "is:resolved",
    },
];

/* Track all active widgets with a Map by stream_id. We have at max
   one for now, but we may eventually allow multiple streams to be
   expanded. */
const active_widgets = new Map<number, LeftSidebarTopicListWidget>();
export let search_pill_widget: SearchPillWidget | null = null;
export let topic_state_typeahead: Typeahead<TopicFilterPill> | undefined;

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
    const $filter = $("#topic_filter_query");
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

export type ListInfoNode = vdom.Node<ListInfoNodeOptions>;

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
        // We return `true` which can possibly lead to missing
        // 'show all topics', even if all the topics are not displayed.
        // The `get_server_history` call above takes care of fetching
        // channel history and rebuilding topic list if needed.
        return true;
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
    topic_list_class_name = "topic-list";
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

        const topic_list_classes: [string] = [this.topic_list_class_name];

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
        this.$parent_elem.find(`.${this.topic_list_class_name}`).remove();
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

        const find = (): JQuery => this.$parent_elem.find(`.${this.topic_list_class_name}`);

        vdom.update(replace_content, find, new_dom, this.prior_dom);

        this.prior_dom = new_dom;
    }

    is_empty(): boolean {
        const $topic_list = this.$parent_elem.find(`.${this.topic_list_class_name}`);
        return !$topic_list.hasClass("topic-list-has-topics");
    }
}

function filter_topics_left_sidebar(topic_names: string[]): string[] {
    const search_term = get_left_sidebar_topic_search_term();
    return topic_list_data.filter_topics_by_search_term(
        topic_names,
        search_term,
        get_typeahead_search_term(),
    );
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

    search_pill_widget?.clear(true);

    const $input = $("#topic_filter_query");
    $input.trigger("blur");
    // Since the `clear` function of the search_pill_widget
    // takes care of clearing both the text content and the
    // pills, we just need to trigger an input event on the
    // contenteditable element to reset the topic list via
    // the `input` event handler without having to manually
    // manage the reset of the topic list.
    $input.trigger("input");
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

export function left_sidebar_scroll_zoomed_in_topic_into_view(): void {
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
            left_sidebar_scroll_zoomed_in_topic_into_view();
            topic_state_typeahead?.lookup(true);
        }
    }

    const spinner = true;
    active_widget.build(spinner);

    stream_topic_history_util.get_server_history(stream_id, on_success);
    left_sidebar_scroll_zoomed_in_topic_into_view();
}

export function get_left_sidebar_topic_search_term(): string {
    return $("#topic_filter_query").text().trim();
}

export function get_typeahead_search_term(): string {
    const $pills = $("#left-sidebar-filter-topic-input .pill");
    const value = $pills.find(".pill-value").text().trim();
    return value;
}

function set_search_bar_text(text: string): void {
    const $input = $("#topic_filter_query");
    $input.text(text);
    $input.trigger("input");
}

export function setup_topic_search_typeahead(): void {
    const $input = $("#topic_filter_query");
    const $pill_container = $("#left-sidebar-filter-topic-input");

    if ($input.length === 0 || $pill_container.length === 0) {
        return;
    }

    search_pill_widget = search_pill.create_pills($pill_container);

    const typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };

    const options = {
        source() {
            const stream_id = active_stream_id();
            assert(stream_id !== undefined);

            if (!stream_topic_history.stream_has_locally_available_resolved_topics(stream_id)) {
                return [];
            }
            const $pills = $("#left-sidebar-filter-topic-input .pill");
            if ($pills.length > 0) {
                return [];
            }
            return [...filter_options];
        },
        item_html(item: TopicFilterPill) {
            return typeahead_helper.render_topic_state(item.label);
        },
        matcher(item: TopicFilterPill, query: string) {
            // This basically only matches if `is:` is in the query.
            return (
                query.includes(":") &&
                (item.syntax.toLowerCase().startsWith(query.toLowerCase()) ||
                    (item.syntax.startsWith("-") &&
                        item.syntax.slice(1).toLowerCase().startsWith(query.toLowerCase())))
            );
        },
        sorter(items: TopicFilterPill[]) {
            // This sort order places "Unresolved topics" first
            // always, which is good because that's almost always what
            // users will want.
            return items;
        },
        updater(item: TopicFilterPill) {
            assert(search_pill_widget !== null);
            search_pill_widget.clear(true);
            search_pill_widget.appendValue(item.syntax);
            set_search_bar_text("");
            $input.trigger("focus");
            return get_left_sidebar_topic_search_term();
        },
        // Prevents key events from propagating to other handlers or
        // triggering default browser actions.
        stopAdvance: true,
        // Use dropup, to match compose typeahead.
        dropup: true,
    };

    topic_state_typeahead = new Typeahead(typeahead_input, options);

    $input.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
        } else if (e.key === ",") {
            e.stopPropagation();
            return;
        }
    });

    search_pill_widget.onPillRemove(() => {
        const stream_id = active_stream_id();
        if (stream_id !== undefined) {
            const widget = active_widgets.get(stream_id);
            if (widget) {
                widget.build();
            }
        }
    });
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

        if (get_left_sidebar_topic_search_term() === "") {
            // When the contenteditable div is empty, the browser
            // adds a <br> element to it, which interferes with
            // the ":empty" selector in the CSS. Hence, we detect
            // this case and clear the content of the div to ensure
            // that the CSS styles are applied correctly.
            // TODO: Remove this when we have a better way to handle
            // empty contenteditable elements. Since while testing this
            // effect in a sandbox, a `display: inline` applied to the
            // contenteditable element seems to fix the issue, but that
            // doesn't work in this particular case.
            // See: https://stackoverflow.com/questions/14638887/br-is-inserted-into-contenteditable-html-element-if-left-empty
            $("#topic_filter_query").empty();
        }
    });
}
