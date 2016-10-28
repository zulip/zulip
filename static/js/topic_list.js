var topic_list = (function () {

var exports = {};

function iterate_to_find(selector, name_to_find, context) {
    // This code is duplicated with stream_list.js, but we should
    // not try to de-dup this; instead, we should try to make it sane
    // for topics and avoid O(N) iteration.
    //
    // We could start by using canonical lowercase values for the
    // data-name attributes (and eventually use topic ids when the
    // back end allows).  Either that, or we should have a data
    // structure that links topic names to list items, so that we
    // don't have to search the DOM at all.
    var lowercase_name = name_to_find.toLowerCase();
    var found = _.find($(selector, context), function (elem) {
        return $(elem).attr('data-name').toLowerCase() === lowercase_name;
    });
    return found ? $(found) : $();
}

exports.remove_expanded_topics = function () {
    popovers.hide_topic_sidebar_popover();
    $("ul.expanded_subjects").remove();
};

function get_topic_filter_li(stream_li, topic) {
    return iterate_to_find(".expanded_subjects li.expanded_subject", topic, stream_li);
}

exports.activate_topic = function (stream_li, active_topic) {
    get_topic_filter_li(stream_li, active_topic).addClass('active-sub-filter');
};

exports.update_count_in_dom = function (count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text('');
    } else {
        count_span.removeClass("zero_count");
        count_span.show();
        value_span.text(count);
    }
};

exports.set_count = function (stream_li, topic, count) {
    var topic_li = get_topic_filter_li(stream_li, topic);
    var count_span = topic_li.find('.subject_count');
    var value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

    exports.update_count_in_dom(count_span, value_span, count);
};

exports.build_list = function (stream, active_topic, max_topics) {
    var topics = stream_data.get_recent_topics(stream) || [];

    if (active_topic) {
        active_topic = active_topic.toLowerCase();
    }

    var display_topics = [];
    var hiding_topics = false;

    _.each(topics, function (subject_obj, idx) {
        var topic_name = subject_obj.subject;
        var num_unread = unread.num_unread_for_subject(stream, subject_obj.canon_subject);

        // Show the most recent topics, as well as any with unread messages
        var always_visible = (idx < max_topics) || (num_unread > 0) || (active_topic === topic_name);

        if (!always_visible) {
            hiding_topics = true;
        }

        var display_subject = {
            topic_name: topic_name,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_muted: muting.is_topic_muted(stream, topic_name),
            zoom_out_hide: !always_visible,
            url: narrow.by_stream_subject_uri(stream, topic_name)
        };
        display_topics.push(display_subject);
    });

    var topic_dom = templates.render('sidebar_subject_list',
                                      {subjects: display_topics,
                                       want_show_more_topics_links: hiding_topics,
                                       stream: stream});

    return topic_dom;
};

exports.rebuild = function (stream_li, stream, active_topic) {
    var max_topics = 5;

    exports.remove_expanded_topics();

    var topic_dom = exports.build_list(stream, active_topic, max_topics);
    stream_li.append(topic_dom);

    if (active_topic) {
        exports.activate_topic(stream_li, active_topic);
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
