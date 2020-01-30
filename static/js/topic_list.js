const render_more_topics = require('../templates/more_topics.hbs');
const render_topic_list_item = require('../templates/topic_list_item.hbs');
const Dict = require('./dict').Dict;
const FoldDict = require('./fold_dict').FoldDict;
const topic_list_data = require('./topic_list_data');

/*
    Track all active widgets with a Dict.

    (We have at max one for now, but we may
    eventually allow multiple streams to be
    expanded.)
*/

const active_widgets = new Dict();

// We know whether we're zoomed or not.
let zoomed = false;

exports.remove_expanded_topics = function () {
    stream_popover.hide_topic_popover();

    _.each(active_widgets.values(), function (widget) {
        widget.remove();
    });

    active_widgets.clear();
};

exports.close = function () {
    zoomed = false;
    exports.remove_expanded_topics();
};

exports.zoom_out = function () {
    zoomed = false;

    const stream_ids = active_widgets.keys();

    if (stream_ids.length !== 1) {
        blueslip.error('Unexpected number of topic lists to zoom out.');
        return;
    }

    const stream_id = stream_ids[0];
    const widget = active_widgets.get(stream_id);
    const parent_widget = widget.get_parent();

    exports.rebuild(parent_widget, stream_id);
};

function update_unread_count(unread_count_elem, count) {
    // unread_count_elem is a jquery element...we expect DOM
    // to look like this:
    //   <div class="topic-unread-count {{#if is_zero}}zero_count{{/if}}">
    //        <div class="value">{{unread}}</div>
    //   </div>
    const value_span = unread_count_elem.find('.value');

    if (value_span.length === 0) {
        blueslip.error('malformed dom for unread count');
        return;
    }

    if (count === 0) {
        unread_count_elem.addClass("zero_count");
        value_span.text('');
    } else {
        unread_count_elem.removeClass("zero_count");
        unread_count_elem.show();
        value_span.text(count);
    }
}

exports.set_count = function (stream_id, topic, count) {
    const widget = active_widgets.get(stream_id);

    if (widget === undefined) {
        return false;
    }

    return widget.set_count(topic, count);
};

exports.widget = function (parent_elem, my_stream_id) {
    const self = {};

    self.build_list = function () {
        const list_info = topic_list_data.get_list_info(
            my_stream_id, zoomed);

        const num_possible_topics = list_info.num_possible_topics;
        const more_topics_unreads = list_info.more_topics_unreads;

        const ul = $('<ul class="topic-list">');

        self.topic_items = new FoldDict();

        // This is the main list of topics:
        //    topic1
        //    topic2
        //    topic3
        _.each(list_info.items, (topic_info) => {
            const li = $(render_topic_list_item(topic_info));
            self.topic_items.set(topic_info.topic_name, li);
            ul.append(li);
        });

        // Now, we decide whether we need to show the "more topics"
        // widget.  We need it if there are at least 5 topics in the
        // frontend's cache, or if we (possibly) don't have all
        // historical topics in the browser's cache.
        const show_more = self.build_more_topics_section(more_topics_unreads);

        const is_showing_all_possible_topics =
            list_info.items.length === num_possible_topics &&
            topic_data.is_complete_for_stream_id(my_stream_id);

        if (!is_showing_all_possible_topics) {
            ul.append(show_more);
        }
        return ul;
    };

    self.build_more_topics_section = function (more_topics_unreads) {
        const show_more_html = render_more_topics({
            more_topics_unreads: more_topics_unreads,
        });
        return $(show_more_html);
    };

    self.get_parent = function () {
        return parent_elem;
    };

    self.get_stream_id = function () {
        return my_stream_id;
    };

    self.get_dom = function () {
        return self.dom;
    };

    self.remove = function () {
        self.dom.remove();
    };

    self.num_items = function () {
        return self.topic_items.num_items();
    };

    self.set_count = function (topic, count) {
        let unread_count_elem;
        if (topic === null) {
            // null is used for updating the "more topics" count.
            if (zoomed) {
                return false;
            }
            const unread_count_parent = $(".show-more-topics");
            if (unread_count_parent.length === 0) {
                // If no show-more-topics element is present in the
                // DOM, there are two possibilities.  The most likely
                // is that there are simply no unreads on that topic
                // and there should continue to not be a "more topics"
                // button; we can check this by looking at count.
                if (count === 0) {
                    return false;
                }

                // The alternative is that there is these new messages
                // create the need for a "more topics" widget with a
                // nonzero unread count, and we need to create one and
                // add it to the DOM.
                //
                // With our current implementation, this code path
                // will always have its results overwritten shortly
                // after, because (1) the can only happen when we just
                // added unread counts, (not removing them), and (2)
                // when learning about new (unread) messages,
                // stream_list.update_dom_with_unread_count is always
                // immediately followed by
                // stream_list.update_streams_sidebar, which will
                // rebuilds the topic list from scratch anyway.
                //
                // So this code mostly exists to document this corner
                // case if in the future we adjust the model for
                // managing unread counts.  The code for updating this
                // element would look something like the following:
                //
                // var show_more = self.build_more_topics_section(count);
                // var topic_list_ul = exports.get_stream_li().find(".topic-list").expectOne();
                // topic_list_ul.append(show_more);
                return false;
            }
            unread_count_elem = unread_count_parent.find(".topic-unread-count");
            update_unread_count(unread_count_elem, count);
            return false;
        }

        if (!self.topic_items.has(topic)) {
            // `topic_li` may not exist if the topic is behind "more
            // topics"; We need to update the "more topics" count
            // instead in that case; we do this by returning true to
            // notify the caller to accumulate these.
            if (muting.is_topic_muted(my_stream_id, topic)) {
                // But we don't count unreads in muted topics.
                return false;
            }
            return true;
        }

        const topic_li = self.topic_items.get(topic);
        unread_count_elem = topic_li.find('.topic-unread-count');
        update_unread_count(unread_count_elem, count);
        return false;
    };

    self.show_spinner = function () {
        // The spinner will go away once we get results and redraw
        // the whole list.
        const spinner = self.dom.find('.searching-for-more-topics');
        spinner.show();
    };

    self.build = function () {
        self.dom = self.build_list();
        parent_elem.append(self.dom);
    };

    return self;
};

exports.active_stream_id = function () {
    const stream_ids = active_widgets.keys();

    if (stream_ids.length !== 1) {
        return;
    }

    return stream_ids[0];
};

exports.get_stream_li = function () {
    const widgets = active_widgets.values();

    if (widgets.length !== 1) {
        return;
    }

    const stream_li = widgets[0].get_parent();
    return stream_li;
};

exports.rebuild = function (stream_li, stream_id) {
    exports.remove_expanded_topics();
    const widget = exports.widget(stream_li, stream_id);
    widget.build();

    active_widgets.set(stream_id, widget);
};

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
exports.zoom_in = function () {
    zoomed = true;

    const stream_id = exports.active_stream_id();
    if (!stream_id) {
        blueslip.error('Cannot find widget for topic history zooming.');
        return;
    }

    const active_widget = active_widgets.get(stream_id);

    function on_success() {
        if (!active_widgets.has(stream_id)) {
            blueslip.warn('User re-narrowed before topic history was returned.');
            return;
        }

        if (!zoomed) {
            blueslip.warn('User zoomed out before topic history was returned.');
            // Note that we could attempt to re-draw the zoomed out topic list
            // here, given that we have more history, but that might be more
            // confusing than helpful to a user who is likely trying to browse
            // other streams.
            return;
        }

        const widget = active_widgets.get(stream_id);

        exports.rebuild(widget.get_parent(), stream_id);
    }

    ui.get_scroll_element($('#stream-filters-container')).scrollTop(0);
    active_widget.show_spinner();
    topic_data.get_server_history(stream_id, on_success);
};

exports.initialize = function () {
    $('#stream_filters').on('click', '.topic-box', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if ($(e.target).closest('.show-more-topics').length > 0) {
            return;
        }

        // In a more componentized world, we would delegate some
        // of this stuff back up to our parents.

        const stream_row = $(e.target).parents('.narrow-filter');
        const stream_id = parseInt(stream_row.attr('data-stream-id'), 10);
        const sub = stream_data.get_sub_by_id(stream_id);
        const topic = $(e.target).parents('li').attr('data-topic-name');

        narrow.activate([
            {operator: 'stream', operand: sub.name},
            {operator: 'topic', operand: topic}],
                        {trigger: 'sidebar'});

        e.preventDefault();
    });
};


window.topic_list = exports;
