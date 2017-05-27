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
    }
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

exports.build_widget = function (parent_elem, my_stream_id, active_topic, max_topics) {
    var self = {};
    self.topic_items = new Dict({fold_case: true});

    var my_stream_name = stream_data.get_sub_by_id(my_stream_id).name;

    function build_list(active_topic, max_topics) {
        var topics = stream_data.get_recent_topics_for_id(my_stream_id) || [];

        if (active_topic) {
            active_topic = active_topic.toLowerCase();
        }

        var hiding_topics = false;

        var ul = $('<ul class="topic-list">');
        ul.attr('data-stream', my_stream_name);

        _.each(topics, function (subject_obj, idx) {
            var show_topic;
            var topic_name = subject_obj.subject;
            var num_unread = unread.num_unread_for_subject(my_stream_id, subject_obj.canon_subject);

            if (zoomed) {
                show_topic = true;
            } else {
                // Show the most recent topics, as well as any with unread messages
                show_topic = (idx < max_topics) || (num_unread > 0) ||
                             (active_topic === topic_name.toLowerCase());

                if (!show_topic) {
                    hiding_topics = true;
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

        if (hiding_topics) {
            var show_more = $('<li class="show-more-topics">');
            show_more.attr('data-stream', my_stream_name);
            var link = $('<a href="#">');
            link.html(i18n.t('more topics'));
            show_more.html(link);
            ul.append(show_more);
        }

        return ul;
    }

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

    self.activate_topic = function (active_topic) {
        var li = self.topic_items.get(active_topic);
        if (li) {
            li.addClass('active-sub-filter');
        }
    };

    self.dom = build_list(active_topic, max_topics);

    parent_elem.append(self.dom);

    if (active_topic) {
        self.activate_topic(active_topic);
    }


    return self;
};

exports.rebuild = function (stream_li, stream_id) {
    var max_topics = 5;

    var active_topic = narrow_state.topic();
    exports.remove_expanded_topics();
    active_widget = exports.build_widget(stream_li, stream_id, active_topic, max_topics);
};

// For zooming, we only do topic-list stuff here...let stream_list
// handle hiding/showing the non-narrowed streams
exports.zoom_in = function () {
    zoomed = true;

    if (!active_widget) {
        blueslip.error('Cannot find widget for topic history zooming.');
        return;
    }

    exports.rebuild(active_widget.get_parent(), active_widget.get_stream_id());
    $('#stream-filters-container').scrollTop(0);
    $('#stream-filters-container').perfectScrollbar('update');
};

exports.zoom_out = function (options) {
    zoomed = false;
    if (options && options.clear_topics) {
        exports.remove_expanded_topics();
    } else {
        exports.rebuild(active_widget.get_parent(), active_widget.get_stream_id());
    }
};

exports.is_zoomed = function () {
    return zoomed;
};

exports.set_click_handlers = function (callbacks) {
    $('#stream_filters').on('click', '.show-more-topics', function (e) {
        callbacks.zoom_in();

        e.preventDefault();
        e.stopPropagation();
    });

    $('.show-all-streams').on('click', function (e) {
        callbacks.zoom_out({clear_topics: false});

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

        var stream = $(e.target).parents('ul').attr('data-stream');
        var topic = $(e.target).parents('li').attr('data-name');

        narrow.activate([{operator: 'stream',  operand: stream},
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
