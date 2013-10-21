var stream_list = (function () {

var exports = {};

var last_private_message_count = 0;
var last_mention_count = 0;
var previous_sort_order;

exports.sort_narrow_list = function () {
    var streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    var sort_recent = (streams.length > 40);

    streams.sort(function (a, b) {
        if (sort_recent) {
            if (recent_subjects.has(b) && ! recent_subjects.has(a)) {
                return 1;
            } else if (! recent_subjects.has(b) && recent_subjects.has(a)) {
                return -1;
            }
        }
        return util.strcmp(a, b);
    });

    if (previous_sort_order !== undefined
        && util.array_compare(previous_sort_order, streams)) {
        return;
    }

    previous_sort_order = streams;

    var parent = $('#stream_filters');
    parent.empty();

    var elems = [];
    _.each(streams, function (stream) {
        var li = $(stream_data.get_sub(stream).sidebar_li);
        if (sort_recent) {
            if (! recent_subjects.has(stream)) {
                li.addClass('inactive_stream');
            } else {
                li.removeClass('inactive_stream');
            }
        }
        elems.push(li.get(0));
    });
    $(elems).appendTo(parent);
};

function iterate_to_find(selector, name_to_find, context) {
    var lowercase_name = name_to_find.toLowerCase();
    var found = _.find($(selector, context), function (elem) {
        return $(elem).attr('data-name').toLowerCase() === lowercase_name;
    });
    return found ? $(found) : $();
}

// TODO: Now that the unread count functions support the user sidebar
// as well, we probably should consider moving them to a different file.
function get_filter_li(type, name) {
    if (type === 'stream') {
        return $("#stream_sidebar_" + subs.stream_id(name));
    } else if (type === "private") {
        return $("li.user_sidebar_entry[data-email='" + name + "']");
    }
    return iterate_to_find("#" + type + "_filters > li", name);
}

function get_subject_filter_li(stream, subject) {
    var stream_li = get_filter_li('stream', stream);
    return iterate_to_find(".expanded_subjects li", subject, stream_li);
}

exports.set_in_home_view = function (stream, in_home) {
    var li = get_filter_li('stream', stream);
    if (in_home) {
        li.removeClass("out_of_home_view");
    } else {
        li.addClass("out_of_home_view");
    }
};

function build_narrow_filter(name, type) {
    var args = {name: name,
                id: subs.stream_id(name),
                uri: narrow.by_stream_uri(name),
                not_in_home_view: (stream_data.in_home_view(name) === false),
                invite_only: stream_data.get_sub(name).invite_only,
                color: stream_data.get_color(name)
               };
    args.dark_background = stream_color.get_color_class(args.color);
    var list_item = $(templates.render('stream_sidebar_row', args));
    $("#" + type + "_filters").append(list_item);
    return list_item;
}

// Adds the sidebar stream name that, when clicked,
// narrows to that stream
function add_narrow_filter(name, type) {
    if (get_filter_li(type, name).length) {
        // already exists
        return false;
    }
    return build_narrow_filter(name, type);
}

exports.get_count = function (type, name) {
    return get_filter_li(type, name).find('.count .value').text();
};

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        if (count_span.parent().hasClass("subscription_block")) {
            count_span.parent(".subscription_block").removeClass("stream-with-count");
        }
        else if (count_span.parent().hasClass("user_sidebar_entry")) {
            count_span.parent(".user_sidebar_entry").removeClass("user-with-count");
        }
        value_span.text('');
        return;
    }

    count_span.show();

    if (count_span.parent().hasClass("subscription_block")) {
        count_span.parent(".subscription_block").addClass("stream-with-count");
    }
    else if (count_span.parent().hasClass("user_sidebar_entry")) {
        count_span.parent(".user_sidebar_entry").addClass("user-with-count");
    }
    value_span.text(count);
}

function set_count(type, name, count) {
    var count_span = get_filter_li(type, name).find('.count');
    var value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
}

function set_count_toggle_button(elem, count) {
    if (count === 0) {
        if (elem.is(':animated')) {
            return elem.stop(true, true).hide();
        }
        return elem.hide(500);
    } else if ((count > 0) && (count < 1000)) {
        elem.show(500);
        return elem.text(count);
    } else {
        elem.show(500);
        return elem.text("1k+");
    }
}

exports.set_subject_count = function (stream, subject, count) {
    var subject_li = get_subject_filter_li(stream, subject);
    var count_span = subject_li.find('.subject_count');
    var value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

    count_span.removeClass("zero_count");
    update_count_in_dom(count_span, value_span, count);
};

exports.remove_narrow_filter = function (name, type) {
    get_filter_li(type, name).remove();
};

function remove_expanded_subjects() {
    popovers.hide_topic_sidebar_popover();
    $("ul.expanded_subjects").remove();
}

function rebuild_recent_subjects(stream, active_topic) {
    // TODO: Call rebuild_recent_subjects less, not on every new
    // message.
    remove_expanded_subjects();
    var max_subjects = 5;
    var stream_li = get_filter_li('stream', stream);
    var subjects = recent_subjects.get(stream) || [];

    if (active_topic) {
        active_topic = active_topic.toLowerCase();
    }

    var display_subjects = [];

    _.each(subjects, function (subject_obj, idx) {
        var topic_name = subject_obj.subject;
        var num_unread = unread.num_unread_for_subject(stream, subject_obj.canon_subject);

        // Show the most recent subjects, as well as any with unread messages
        if ((idx < max_subjects) || (num_unread > 0) || (active_topic === topic_name)) {
            var display_subject = {
                topic_name: topic_name,
                unread: num_unread,
                is_zero: num_unread === 0,
                is_muted: muting.is_topic_muted(stream, topic_name),
                url: narrow.by_stream_subject_uri(stream, topic_name)
            };
            display_subjects.push(display_subject);
        }
    });

    stream_li.append(templates.render('sidebar_subject_list',
                                      {subjects: display_subjects,
                                       stream: stream}));

    if (active_topic) {
        get_subject_filter_li(stream, active_topic).addClass('active-subject-filter');
    }
}

exports.update_streams_sidebar = function () {
    exports.sort_narrow_list();

    if (! narrow.active()) {
        return;
    }

    var op_stream = narrow.filter().operands('stream');
    var op_subject = narrow.filter().operands('topic');
    var subject;
    if (op_stream.length !== 0) {
        if (op_subject.length !== 0) {
            subject = op_subject[0];
        }
        if (stream_data.is_subscribed(op_stream[0])) {
            rebuild_recent_subjects(op_stream[0], subject);
        }
    }
};

function do_new_messages_animation(message_type) {
    var li = get_filter_li("global", message_type);
    li.addClass("new_messages");
    function mid_animation() {
        li.removeClass("new_messages");
        li.addClass("new_messages_fadeout");
    }
    function end_animation() {
        li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

function animate_private_message_changes(new_private_message_count) {
    if (new_private_message_count > last_private_message_count) {
        do_new_messages_animation('private');
    }
    last_private_message_count = new_private_message_count;
}

function animate_mention_changes(new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation('mentioned');
    }
    last_mention_count = new_mention_count;
}


exports.set_presence_list_count = function (person, count) {
    set_count("private", person, count);
};

exports.update_dom_with_unread_counts = function (counts) {
    // counts is just a data object that gets calculated elsewhere
    // Our job is to update some DOM elements.

    // counts.stream_count maps streams to counts
    counts.stream_count.each(function (count, stream) {
        set_count("stream", stream, count);
    });

    // counts.subject_count maps streams to hashes of subjects to counts
    counts.subject_count.each(function (subject_hash, stream) {
        subject_hash.each(function (count, subject) {
            exports.set_subject_count(stream, subject, count);
        });
    });


    counts.pm_count.each(function (count, person) {
        exports.set_presence_list_count(person, count);
    });

    // integer counts
    set_count("global", "private", counts.private_message_count);
    set_count("global", "mentioned", counts.mentioned_message_count);
    set_count("global", "home", counts.home_unread_messages);

    set_count_toggle_button($("#streamlist-toggle-unreadcount"), counts.home_unread_messages);
    set_count_toggle_button($("#userlist-toggle-unreadcount"), counts.private_message_count);

    animate_private_message_changes(counts.private_message_count);
    animate_mention_changes(counts.mentioned_message_count);
};

exports.rename_stream = function (sub) {
    sub.sidebar_li = build_narrow_filter(sub.name, "stream");
    exports.sort_narrow_list(); // big hammer
};

$(function () {
    $(document).on('narrow_activated.zulip', function (event) {
        $("ul.filters li").removeClass('active-filter active-subject-filter');
        remove_expanded_subjects();

        // TODO: handle confused filters like "in:all stream:foo"
        var op_in = event.filter.operands('in');
        if (op_in.length !== 0) {
            if (['all', 'home'].indexOf(op_in[0]) !== -1) {
                $("#global_filters li[data-name='" + op_in[0] + "']").addClass('active-filter');
            }
        }
        var op_is = event.filter.operands('is');
        if (op_is.length !== 0) {
            if (['private', 'starred', 'mentioned'].indexOf(op_is[0]) !== -1) {
                $("#global_filters li[data-name='" + op_is[0] + "']").addClass('active-filter');
            }
        }
        var op_stream = event.filter.operands('stream');
        if (op_stream.length !== 0 && stream_data.is_subscribed(op_stream[0])) {
            var stream_li = get_filter_li('stream', op_stream[0]);
            var op_subject = event.filter.operands('topic');
            var subject;
            if (op_subject.length !== 0) {
                subject = op_subject[0];
            } else {
                stream_li.addClass('active-filter');
            }
            rebuild_recent_subjects(op_stream[0], subject);
            process_visible_unread_messages();
        }
        var op_pm = event.filter.operands('pm-with');
        if (op_pm.length === 1) {
            $("#user_presences li[data-email='" + op_pm[0] + "']").addClass('active-filter');
        }
    });

    $(document).on('narrow_deactivated.zulip', function (event) {
        $("ul.filters li").removeClass('active-filter active-subject-filter');
        remove_expanded_subjects();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('sub_obj_created.zulip', function (event) {
        if (event.sub.subscribed) {
            var stream_name = event.sub.name;
            var li = add_narrow_filter(stream_name, "stream");
            if (li) {
                event.sub.sidebar_li = li;
            }
        }
    });

    $(document).on('subscription_add_done.zulip', function (event) {
        var stream_name = event.sub.name;
        var li = add_narrow_filter(stream_name, "stream");
        if (li) {
            event.sub.sidebar_li = li;
        }
        exports.sort_narrow_list();
    });

    $(document).on('subscription_remove_done.zulip', function (event) {
        var stream_name = event.sub.name;
        exports.remove_narrow_filter(stream_name, 'stream');
        // We need to make sure we resort if the removed sub gets added again
        previous_sort_order = undefined;
    });
});

return exports;
}());
