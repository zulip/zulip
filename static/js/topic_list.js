const render_more_topics = require('../templates/more_topics.hbs');
const render_topic_list_item = require('../templates/topic_list_item.hbs');
const Dict = require('./dict').Dict;
const FoldDict = require('./fold_dict').FoldDict;

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
        self.topic_items = new FoldDict();
        let topics_selected = 0;
        let more_topics_unreads = 0;

        const max_topics = 5;
        const max_topics_with_unread = 8;
        const topic_names = topic_data.get_recent_names(my_stream_id);

        const ul = $('<ul class="topic-list">');

        _.each(topic_names, function (topic_name, idx) {
            const num_unread = unread.num_unread_for_topic(my_stream_id, topic_name);
            const is_active_topic = self.active_topic === topic_name.toLowerCase();
            const is_topic_muted = muting.is_topic_muted(my_stream_id, topic_name);

            if (!zoomed) {
                function should_show_topic() {
                    // This function exists just for readability, to
                    // avoid long chained conditionals to determine
                    // which topics to include.

                    // We always show the active topic.  Ideally, this
                    // logic would first check whether the active
                    // topic is in the set of those with unreads to
                    // avoid ending up with max_topics_with_unread + 1
                    // total topics if the active topic comes after
                    // the first several topics with unread messages.
                    if (is_active_topic) {
                        return true;
                    }

                    // We unconditionally skip showing muted topics
                    // when not zoomed, even if they have unread
                    // messages.
                    if (is_topic_muted) {
                        return false;
                    }

                    // We include the most recent max_topics topics,
                    // even if there are no unread messages.
                    if (idx < max_topics) {
                        return true;
                    }

                    // We include older topics with unread messages up
                    // until max_topics_with_unread total topics have
                    // been included.
                    if (num_unread > 0 && topics_selected < max_topics_with_unread) {
                        return true;
                    }

                    // Otherwise, we don't show the topic in the
                    // unzoomed view.  We might display its unread
                    // count in in "more topics" if it is not muted.
                    return false;
                }

                const show_topic = should_show_topic();
                if (!show_topic) {
                    if (!is_topic_muted) {
                        // The "more topics" unread count, like
                        // stream-level counts, only counts messages
                        // on unmuted topics.
                        more_topics_unreads += num_unread;
                    }
                    return;
                }
                topics_selected += 1;
                // We fall through to rendering the topic, using the
                // same code we do when zoomed.
            }

            const topic_info = {
                topic_name: topic_name,
                unread: num_unread,
                is_zero: num_unread === 0,
                is_muted: is_topic_muted,
                url: hash_util.by_stream_topic_uri(my_stream_id, topic_name),
            };
            const li = $(render_topic_list_item(topic_info));
            self.topic_items.set(topic_name, li);
            ul.append(li);
        });

        // Now, we decide whether we need to show the "more topics"
        // widget.  We need it if there are at least 5 topics in the
        // frontend's cache, or if we (possibly) don't have all
        // historical topics in the browser's cache.
        const show_more = self.build_more_topics_section(more_topics_unreads);
        const sub = stream_data.get_sub_by_id(my_stream_id);

        if (topic_names.length > max_topics || !stream_data.all_topics_in_cache(sub)) {
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

    self.activate_topic = function () {
        const li = self.topic_items.get(self.active_topic);
        if (li) {
            li.addClass('active-sub-filter');
        }
    };

    self.show_spinner = function () {
        // The spinner will go away once we get results and redraw
        // the whole list.
        const spinner = self.dom.find('.searching-for-more-topics');
        spinner.show();
    };

    self.show_no_more_topics = function () {
        const elem = self.dom.find('.no-more-topics-found');
        elem.show();
        self.no_more_topics = true;
    };

    self.build = function (active_topic, no_more_topics) {
        self.no_more_topics = false; // for now

        if (active_topic) {
            active_topic = active_topic.toLowerCase();
        }
        self.active_topic = active_topic;

        self.dom = self.build_list();

        parent_elem.append(self.dom);

        // We often rebuild an entire topic list, and the
        // caller will pass us in no_more_topics as true
        // if we were showing "No more topics found" from
        // the initial zooming.
        if (no_more_topics) {
            self.show_no_more_topics();
        }

        if (active_topic) {
            self.activate_topic();
        }
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

exports.need_to_show_no_more_topics = function (stream_id) {
    // This function is important, and the use case here is kind of
    // subtle.  We do complete redraws of the topic list when new
    // messages come in, and we don't want to overwrite the
    // "no more topics" error message.
    if (!zoomed) {
        return false;
    }

    if (!active_widgets.has(stream_id)) {
        return false;
    }

    const widget = active_widgets.get(stream_id);

    return widget.no_more_topics;
};

exports.rebuild = function (stream_li, stream_id) {
    const active_topic = narrow_state.topic();
    const no_more_topics = exports.need_to_show_no_more_topics(stream_id);

    exports.remove_expanded_topics();
    const widget = exports.widget(stream_li, stream_id);
    widget.build(active_topic, no_more_topics);

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

    const before_count = active_widget.num_items();

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

        const after_count = widget.num_items();

        if (after_count === before_count) {
            widget.show_no_more_topics();
        }
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
