"use strict";

const _ = require("lodash");

const render_more_topics = require("../templates/more_topics.hbs");
const render_more_topics_spinner = require("../templates/more_topics_spinner.hbs");
const render_topic_list_item = require("../templates/topic_list_item.hbs");

const topic_list_data = require("./topic_list_data");

/*
    Track all active widgets with a Map.

    (We have at max one for now, but we may
    eventually allow multiple streams to be
    expanded.)
*/

const active_widgets = new Map();

// We know whether we're zoomed or not.
let zoomed = false;

exports.update = function () {
    for (const widget of active_widgets.values()) {
        widget.build();
    }
};

exports.clear = function () {
    stream_popover.hide_topic_popover();

    for (const widget of active_widgets.values()) {
        widget.remove();
    }

    active_widgets.clear();
};

exports.close = function () {
    zoomed = false;
    exports.clear();
};

exports.zoom_out = function () {
    zoomed = false;

    const stream_ids = Array.from(active_widgets.keys());

    if (stream_ids.length !== 1) {
        blueslip.error("Unexpected number of topic lists to zoom out.");
        return;
    }

    const stream_id = stream_ids[0];
    const widget = active_widgets.get(stream_id);
    const parent_widget = widget.get_parent();

    exports.rebuild(parent_widget, stream_id);
};

exports.keyed_topic_li = (convo) => {
    const render = () => render_topic_list_item(convo);

    const eq = (other) => _.isEqual(convo, other.convo);

    const key = "t:" + convo.topic_name;

    return {
        key,
        render,
        convo,
        eq,
    };
};

exports.more_li = (more_topics_unreads) => {
    const render = () =>
        render_more_topics({
            more_topics_unreads,
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
};

exports.spinner_li = () => {
    const render = () => render_more_topics_spinner();

    const eq = (other) => other.spinner;

    const key = "more";

    return {
        key,
        spinner: true,
        render,
        eq,
    };
};

class TopicListWidget {
    prior_dom = undefined;

    constructor(parent_elem, my_stream_id) {
        this.parent_elem = parent_elem;
        this.my_stream_id = my_stream_id;
    }

    build_list(spinner) {
        const list_info = topic_list_data.get_list_info(this.my_stream_id, zoomed);

        const num_possible_topics = list_info.num_possible_topics;
        const more_topics_unreads = list_info.more_topics_unreads;

        const is_showing_all_possible_topics =
            list_info.items.length === num_possible_topics &&
            stream_topic_history.is_complete_for_stream_id(this.my_stream_id);

        const attrs = [["class", "topic-list"]];

        const nodes = list_info.items.map((convo) => exports.keyed_topic_li(convo));

        if (spinner) {
            nodes.push(exports.spinner_li());
        } else if (!is_showing_all_possible_topics) {
            nodes.push(exports.more_li(more_topics_unreads));
        }

        const dom = vdom.ul({
            attrs,
            keyed_nodes: nodes,
        });

        return dom;
    }

    get_parent() {
        return this.parent_elem;
    }

    get_stream_id() {
        return this.my_stream_id;
    }

    remove() {
        this.parent_elem.find(".topic-list").remove();
        this.prior_dom = undefined;
    }

    build(spinner) {
        const new_dom = this.build_list(spinner);

        const replace_content = (html) => {
            this.remove();
            this.parent_elem.append(html);
        };

        const find = () => this.parent_elem.find(".topic-list");

        vdom.update(replace_content, find, new_dom, this.prior_dom);

        this.prior_dom = new_dom;
    }
}
exports.TopicListWidget = TopicListWidget;

exports.active_stream_id = function () {
    const stream_ids = Array.from(active_widgets.keys());

    if (stream_ids.length !== 1) {
        return undefined;
    }

    return stream_ids[0];
};

exports.get_stream_li = function () {
    const widgets = Array.from(active_widgets.values());

    if (widgets.length !== 1) {
        return undefined;
    }

    const stream_li = widgets[0].get_parent();
    return stream_li;
};

exports.rebuild = function (stream_li, stream_id) {
    const active_widget = active_widgets.get(stream_id);

    if (active_widget) {
        active_widget.build();
        return;
    }

    exports.clear();
    const widget = new TopicListWidget(stream_li, stream_id);
    widget.build();

    active_widgets.set(stream_id, widget);
};

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
exports.zoom_in = function () {
    zoomed = true;

    const stream_id = exports.active_stream_id();
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

    ui.get_scroll_element($("#stream-filters-container")).scrollTop(0);

    const spinner = true;
    active_widget.build(spinner);

    stream_topic_history.get_server_history(stream_id, on_success);
};

exports.initialize = function () {
    $("#stream_filters").on("click", ".topic-box", (e) => {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if ($(e.target).closest(".show-more-topics").length > 0) {
            return;
        }

        // In a more componentized world, we would delegate some
        // of this stuff back up to our parents.

        const stream_row = $(e.target).parents(".narrow-filter");
        const stream_id = Number.parseInt(stream_row.attr("data-stream-id"), 10);
        const sub = stream_data.get_sub_by_id(stream_id);
        const topic = $(e.target).parents("li").attr("data-topic-name");

        narrow.activate(
            [
                {operator: "stream", operand: sub.name},
                {operator: "topic", operand: topic},
            ],
            {trigger: "sidebar"},
        );

        e.preventDefault();
    });
};

window.topic_list = exports;
