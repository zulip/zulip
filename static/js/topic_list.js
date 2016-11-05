var topic_list = (function () {

var exports = {};

var widgets = new Dict({fold_case: true}); // key is stream_name

exports.remove_expanded_topics = function () {
    popovers.hide_topic_sidebar_popover();
    $("ul.topic-list").remove();
};


function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text('');
    } else {
        count_span.removeClass("zero_count");
        count_span.show();
        value_span.text(count);
    }
}

exports.set_count = function (stream_name, topic, count) {
    if (!widgets.has(stream_name)) {
        // fail silently here...sometimes we haven't build
        // the widget yet, especially during page loading
        return;
    }

    var widget = widgets.get(stream_name);
    widget.set_count(topic, count);
};

exports.build_widget = function (stream, active_topic, max_topics) {
    var self = {};
    self.topic_items = new Dict({fold_case: true});

    function build_list(stream, active_topic, max_topics) {
        var topics = stream_data.get_recent_topics(stream) || [];

        if (active_topic) {
            active_topic = active_topic.toLowerCase();
        }

        var hiding_topics = false;

        var ul = $('<ul class="topic-list">');
        ul.attr('data-stream', stream);

        _.each(topics, function (subject_obj, idx) {
            var topic_name = subject_obj.subject;
            var num_unread = unread.num_unread_for_subject(stream, subject_obj.canon_subject);

            // Show the most recent topics, as well as any with unread messages
            var always_visible = (idx < max_topics) || (num_unread > 0) ||
                                 (active_topic === topic_name);

            if (!always_visible) {
                hiding_topics = true;
            }

            var topic_info = {
                topic_name: topic_name,
                unread: num_unread,
                is_zero: num_unread === 0,
                is_muted: muting.is_topic_muted(stream, topic_name),
                zoom_out_hide: !always_visible,
                url: narrow.by_stream_subject_uri(stream, topic_name)
            };
            var li = $(templates.render('topic_list_item', topic_info));
            self.topic_items.set(topic_name, li);
            ul.append(li);
        });

        if (hiding_topics) {
            var show_more = $('<li class="show-more-topics">');
            show_more.attr('data-stream', stream);
            var link = $('<a href="#">');
            link.html(i18n.t('more topics'));
            show_more.html(link);
            ul.append(show_more);
        }

        widgets.set(stream, self);

        return ul;
    }

    self.get_dom = function () {
        return self.dom;
    };

    self.set_count = function (topic, count) {
        if (!self.topic_items.has(topic)) {
            blueslip.error('set_count fails for topic ' + topic);
            return;
        }
        var topic_li = self.topic_items.get(topic);

        var count_span = topic_li.find('.subject_count');
        var value_span = count_span.find('.value');

        if (count_span.length === 0 || value_span.length === 0) {
            return;
        }

        update_count_in_dom(count_span, value_span, count);
    };

    self.activate_topic = function (active_topic) {
        var li = self.topic_items.get(active_topic);
        if (li) {
            li.addClass('active-sub-filter');
        }
    };

    self.dom = build_list(stream, active_topic, max_topics);

    return self;
};

exports.rebuild = function (stream_li, stream, active_topic) {
    var max_topics = 5;

    exports.remove_expanded_topics();

    var widget = exports.build_widget(stream, active_topic, max_topics);
    stream_li.append(widget.get_dom());

    if (active_topic) {
        widget.activate_topic(active_topic);
    }
};

exports.set_click_handlers = function (callbacks) {
    $('#stream_filters').on('click', '.show-more-topics', function (e) {
        callbacks.zoom_in();

        e.preventDefault();
        e.stopPropagation();
    });

    $('.show-all-streams').on('click', function (e) {
        callbacks.zoom_out();

        e.preventDefault();
        e.stopPropagation();
    });

    $('#stream_filters').on('click', '.subject_box', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }

        // In a more componentized world, we would delegate some
        // of this stuff back up to our parents.
        if (ui.home_tab_obscured()) {
            ui.change_tab_to('#home');
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
