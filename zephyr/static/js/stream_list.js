var stream_list = (function () {

var exports = {};

var last_private_message_count = 0;
var last_mention_count = 0;
var previous_sort_order;

exports.sort_narrow_list = function () {
    var streams = subs.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    var sort_recent = (streams.length > 40);

    streams.sort(function(a, b) {
        if (sort_recent) {
            if (recent_subjects[b] !== undefined &&
                recent_subjects[a] === undefined) {
                return 1;
            } else if (recent_subjects[b] === undefined &&
                       recent_subjects[a] !== undefined) {
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
    $.each(streams, function(i, stream) {
        // TODO: we should export the sub objects better
        var li = $(subs.have(stream).sidebar_li);
        if (sort_recent) {
            if (recent_subjects[stream] === undefined) {
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
    var retval = $();
    $(selector, context).each(function (idx, elem) {
        var jelem = $(elem);
        var elem_name = jelem.attr('data-name');
        if (elem_name.toLowerCase() === name_to_find.toLowerCase()) {
            retval = jelem;
            return false;
        }
    });
    return retval;
}

// TODO: Now that the unread count functions support the user sidebar
// as well, we probably should consider moving them to a different file.
function get_filter_li(type, name) {
    if (type === 'stream') {
        return $("#stream_sidebar_" + subs.stream_id(name));
    } else if (type === "private") {
        return $(".user_sidebar_entry > a[data-email='" + name + "']");
    }
    return iterate_to_find("#" + type + "_filters > li", name);
}

function get_subject_filter_li(stream, subject) {
    var stream_li = get_filter_li('stream', stream);
    return iterate_to_find(".expanded_subjects li", subject, stream_li);
}

// Adds the sidebar stream name that, when clicked,
// narrows to that stream
function add_narrow_filter(name, type) {
    if (get_filter_li(type, name).length) {
        // already exists
        return false;
    }

    var args = {name: name,
                id: subs.stream_id(name),
                uri: narrow.by_stream_uri(name),
                not_in_home_view: (subs.have(name).in_home_view === false),
                invite_only: subs.have(name).invite_only,
                color: subs.get_color(name)};
    var list_item = templates.render('stream_sidebar_row', args);
    $("#" + type + "_filters").append(list_item);
    return list_item;
}

exports.get_count = function (type, name) {
    return get_filter_li(type, name).find('.count .value').text();
};

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        value_span.text('');
        return;
    }

    count_span.show();
    value_span.text(count);
}

exports.set_count = function (type, name, count) {
    var count_span = get_filter_li(type, name).find('.count');
    var value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
};

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

exports.remove_all_narrow_filters = function () {
    $("#stream_filters").children().remove();
};

function rebuild_recent_subjects(stream, subject) {
    $('.expanded_subjects').remove();
    var stream_li = get_filter_li('stream', stream);
    var subjects = recent_subjects[stream] || [];
    var active_orig_subject = subject;
    $.each(subjects, function (idx, subject_obj) {
        var num_unread = unread.num_unread_for_subject(stream, subject_obj.canon_subject);
        subject_obj.unread = num_unread;
        subject_obj.is_zero = num_unread === 0;

        if (subject === subject_obj.canon_subject) {
            active_orig_subject = subject_obj.subject;
        }
    });


    stream_li.append(templates.render('sidebar_subject_list',
                                      {subjects: subjects,
                                       stream: stream}));

    if (active_orig_subject !== undefined) {
        get_subject_filter_li(stream, active_orig_subject).addClass('active-subject-filter');
    }
}

exports.update_streams_sidebar = function () {
    exports.sort_narrow_list();

    if (! narrow.active()) {
        return;
    }

    var op_stream = narrow.filter().operands('stream');
    var op_subject = narrow.filter().operands('subject');
    var subject;
    if (op_stream.length !== 0) {
        if (op_subject.length !== 0) {
            subject = op_subject[0];
        }
        if (subs.have(op_stream[0])) {
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
        do_new_messages_animation('private-message');
    }
    last_private_message_count = new_private_message_count;
}

function animate_mention_changes(new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation('mentioned-message');
    }
    last_mention_count = new_mention_count;
}

exports.update_dom_with_unread_counts = function (counts) {
    // counts is just a data object that gets calculated elsewhere
    // Our job is to update some DOM elements.

    // counts.stream_count maps streams to counts
    $.each(counts.stream_count, function(stream, count) {
        exports.set_count("stream", stream, count);
    });

    // counts.subject_count maps streams to hashes of subjects to counts
    $.each(counts.subject_count, function(stream, subject_hash) {
        $.each(subject_hash, function(subject, count) {
            exports.set_subject_count(stream, subject, count);
        });
    });

    // counts.pm_count maps people to counts
    $.each(counts.pm_count, function(person, count) {
        exports.set_count("private", person, count);
    });

    // integer counts
    exports.set_count("global", "private-message", counts.private_message_count);
    exports.set_count("global", "mentioned-message", counts.mentioned_message_count);
    exports.set_count("global", "home", counts.home_unread_messages);

    animate_private_message_changes(counts.private_message_count);
    animate_mention_changes(counts.mentioned_message_count);
};

$(function () {
    $(document).on('narrow_activated.zephyr', function (event) {
        $("ul.filters li").removeClass('active-filter active-subject-filter');

        // TODO: handle confused filters like "in:all stream:foo"
        var op_in = event.filter.operands('in');
        if (op_in.length !== 0) {
            if (['all', 'home'].indexOf(op_in[0]) !== -1) {
                $("#global_filters li[data-name='" + op_in[0] + "']").addClass('active-filter');
            }
        }
        var op_is = event.filter.operands('is');
        if (op_is.length !== 0) {
            if (['private-message', 'starred', 'mentioned'].indexOf(op_is[0]) !== -1) {
                $("#global_filters li[data-name='" + op_is[0] + "']").addClass('active-filter');
            }
        }
        var op_stream = event.filter.operands('stream');
        if (op_stream.length !== 0 && subs.have(op_stream[0])) {
            var stream_li = get_filter_li('stream', op_stream[0]);
            var op_subject = event.filter.operands('subject');
            var subject;
            if (op_subject.length !== 0) {
                subject = op_subject[0];
            } else {
                stream_li.addClass('active-filter');
            }
            rebuild_recent_subjects(op_stream[0], subject);
        }
        process_visible_unread_messages();
    });

    $(document).on('narrow_deactivated.zephyr', function (event) {
        $("ul.filters li").removeClass('active-filter active-subject-filter');
        $("ul.expanded_subjects").remove();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('sub_obj_created.zephyr', function (event) {
        if (event.sub.subscribed) {
            var stream_name = event.sub.name;
            var li = add_narrow_filter(stream_name, "stream");
            if (li) {
                event.sub.sidebar_li = li;
            }
        }
    });

    $(document).on('subscription_add_done.zephyr', function (event) {
        var stream_name = event.sub.name;
        var li = add_narrow_filter(stream_name, "stream");
        if (li) {
            event.sub.sidebar_li = li;
        }
        exports.sort_narrow_list();
    });

    $(document).on('subscription_remove_done.zephyr', function (event) {
        var stream_name = event.sub.name;
        exports.remove_narrow_filter(stream_name, 'stream');
        // We need to make sure we resort if the removed sub gets added again
        previous_sort_order = undefined;
    });
});

return exports;
}());
