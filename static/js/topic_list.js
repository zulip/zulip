var topic_list = (function () {

var exports = {};

// We can only ever have one active widget.
var active_widget;

// We know whether we're zoomed or not.
var zoomed = false;

exports.remove_expanded_topics = function () {
    stream_popover.hide_topic_popover();

    if (active_widget) {
        active_widget.remove();
        active_widget = undefined;
    }
};

exports.close = function () {
    zoomed = false;
    exports.remove_expanded_topics();
};

exports.zoom_out = function () {
    zoomed = false;
    exports.rebuild(active_widget.get_parent(), active_widget.get_stream_id());
};

function update_unread_count(unread_count_elem, count) {
    // unread_count_elem is a jquery element...we expect DOM
    // to look like this:
    //   <div class="topic-unread-count {{#if is_zero}}zero_count{{/if}}">
    //        <div class="value">{{unread}}</div>
    //   </div>
    var value_span = unread_count_elem.find('.value');

    if (value_span.length === 0) {
        blueslip.error('malformed dom for unread count');
        return;
    }

    if (count === 0) {
        unread_count_elem.hide();
        value_span.text('');
    } else {
        unread_count_elem.removeClass("zero_count");
        unread_count_elem.show();
        value_span.text(count);
    }
}

exports.set_count = function (stream_id, topic, count) {
    if (active_widget && active_widget.is_for_stream(stream_id)) {
        active_widget.set_count(topic, count);
    }
};

exports.widget = function (parent_elem, my_stream_id) {
    var self = {};

    self.build_list = function () {
        self.topic_items = new Dict({fold_case: true});

        var max_topics = 5;
        var topic_names = topic_data.get_recent_names(my_stream_id);
        var my_stream_name = stream_data.get_sub_by_id(my_stream_id).name;

        var ul = $('<ul class="topic-list">');
        ul.attr('data-stream', my_stream_name);

        _.each(topic_names, function (topic_name, idx) {
            var num_unread = unread.num_unread_for_topic(my_stream_id, topic_name);

            if (!zoomed) {
                // Show the most recent topics, as well as any with unread messages
                var show_topic = (idx < max_topics) || (num_unread > 0) ||
                                 (self.active_topic === topic_name.toLowerCase());

                if (!show_topic) {
                    return;
                }
            }

            var topic_info = {
                topic_name: topic_name,
                unread: num_unread,
                is_zero: num_unread === 0,
                is_muted: muting.is_topic_muted(my_stream_name, topic_name),
                url: narrow.by_stream_subject_uri(my_stream_name, topic_name),
            };
            var li = $(templates.render('topic_list_item', topic_info));
            self.topic_items.set(topic_name, li);
            ul.append(li);
        });

        var show_more = self.build_more_topics_section();
        ul.append(show_more);

        return ul;
    };

    self.build_more_topics_section = function () {
        var show_more_html = templates.render('more_topics');
        return $(show_more_html);
    };

    self.get_parent = function () {
        return parent_elem;
    };

    self.is_for_stream = function (stream_id) {
        return stream_id === my_stream_id;
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
        if (!self.topic_items.has(topic)) {
            // This can happen for truncated topic lists.  No need
            // to warn about it.
            return;
        }
        var topic_li = self.topic_items.get(topic);
        var unread_count_elem = topic_li.find('.topic-unread-count').expectOne();

        update_unread_count(unread_count_elem, count);
    };

    self.activate_topic = function () {
        var li = self.topic_items.get(self.active_topic);
        if (li) {
            li.addClass('active-sub-filter');
        }
    };

    self.show_spinner = function () {
        // The spinner will go away once we get results and redraw
        // the whole list.
        var spinner = self.dom.find('.searching-for-more-topics');
        spinner.show();
    };

    self.show_no_more_topics = function () {
        var elem = self.dom.find('.no-more-topics-found');
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
    if (!active_widget) {
        return;
    }

    return active_widget.get_stream_id();
};

exports.need_to_show_no_more_topics = function (stream_id) {
    // This function is important, and the use case here is kind of
    // subtle.  We do complete redraws of the topic list when new
    // messages come in, and we don't want to overwrite the
    // "no more topics" error message.
    if (!zoomed) {
        return false;
    }

    if (stream_id !== active_widget.get_stream_id()) {
        return false;
    }

    return active_widget.no_more_topics;
};

exports.rebuild = function (stream_li, stream_id) {
    var active_topic = narrow_state.topic();
    var no_more_topics = exports.need_to_show_no_more_topics(stream_id);

    exports.remove_expanded_topics();
    active_widget = exports.widget(stream_li, stream_id);
    active_widget.build(active_topic, no_more_topics);
};

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
exports.zoom_in = function () {
    zoomed = true;

    if (!active_widget) {
        blueslip.error('Cannot find widget for topic history zooming.');
        return;
    }

    var stream_id = active_widget.get_stream_id();
    var before_count = active_widget.num_items();

    function on_success() {
        if ((!active_widget) || (stream_id !== active_widget.get_stream_id())) {
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

        exports.rebuild(active_widget.get_parent(), stream_id);

        var after_count = active_widget.num_items();

        if (after_count === before_count) {
            active_widget.show_no_more_topics();
        }

        ui.update_scrollbar($("#stream-filters-container"));
    }

    $('#stream-filters-container').scrollTop(0);
    ui.update_scrollbar($("#stream-filters-container"));
    active_widget.show_spinner();
    topic_data.get_server_history(stream_id, on_success);
};

exports.set_click_handlers = function (callbacks) {
    $('#stream_filters').on('click', '.show-more-topics', function (e) {
        callbacks.zoom_in({
            stream_id: active_widget.get_stream_id(),
        });

        e.preventDefault();
        e.stopPropagation();
    });

    $('.show-all-streams').on('click', function (e) {
        callbacks.zoom_out({
            stream_li: active_widget.get_parent(),
        });

        e.preventDefault();
        e.stopPropagation();
    });

    $('#stream_filters').on('click', '.topic-box', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }

        // In a more componentized world, we would delegate some
        // of this stuff back up to our parents.
        if (overlays.is_active()) {
            ui_util.change_tab_to('#home');
        }

        var stream_id = $(e.target).parents('.narrow-filter').attr('data-stream-id');
        var sub = stream_data.get_sub_by_id(stream_id);
        var topic = $(e.target).parents('li').attr('data-topic-name');

        narrow.activate([{operator: 'stream', operand: sub.name},
                         {operator: 'topic', operand: topic}],
                        {select_first_unread: true, trigger: 'sidebar'});

        e.preventDefault();
    });
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = topic_list;
}
