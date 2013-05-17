var stream_list = (function () {

var exports = {};

var last_private_message_count = 0;
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

function iterate_to_find(selector, data_name, context) {
    var retval = $();
    $(selector, context).each(function (idx, elem) {
        var jelem = $(elem);
        if (jelem.attr('data-name') === data_name) {
            retval = jelem;
            return false;
        }
    });
    return retval;
}

function get_filter_li(type, name) {
    if (type === 'stream') {
        return $("#stream_sidebar_" + subs.stream_id(name));
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
    var uri = narrow.by_stream_uri(name);
    var list_item;

    if (get_filter_li(type, name).length) {
        // already exists
        return false;
    }

    // For some reason, even though the span is inline-block, if it is empty it
    // takes up no space and you don't see the background color. Thus, add a
    // &nbsp; to get the inline-block behavior we want.
    var swatch = $('<span/>').attr('id', "stream_sidebar_swatch_" + subs.stream_id(name))
                             .addClass('streamlist_swatch')
                             .css('background-color', subs.get_color(name)).html("&nbsp;");
    list_item = $('<li>').attr('data-name', name)
                         .addClass("narrow-filter")
                         .html(swatch);
    if (type === 'stream') {
        list_item.attr('id', "stream_sidebar_" + subs.stream_id(name));
        if (subs.have(name).in_home_view === false) {
            list_item.addClass("out_of_home_view");
        }
    }

    list_item.append($('<a>').attr('href', uri)
                     .addClass('subscription_name')
                     .text(name)
                     .append('<span class="count">(<span class="value"></span>)</span>'))
             .append('<span class="arrow pull-right">▽</span>');
    if (type === "stream" && subs.have(name).invite_only) {
        list_item.append("<i class='icon-lock'/>");
    }
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
    var count_span = get_subject_filter_li(stream, subject).find('.subject_count');
    var value_span = count_span.find('.value');

    if (count_span.length === 0 || value_span.length === 0) {
        return;
    }

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
    $.each(subjects, function (idx, subject_obj) {
        var num_unread = unread.num_unread_for_subject(stream, subject_obj.subject);
        subject_obj.unread = num_unread;
        subject_obj.has_unread = num_unread !== 0;
    });


    stream_li.append(templates.render('sidebar_subject_list',
                                      {subjects: subjects,
                                       stream: stream}));
    if (subject !== undefined) {
        get_subject_filter_li(stream, subject).addClass('active-subject-filter');
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

function do_new_private_messages_animation() {
    var li = get_filter_li("global", "private-message");
    li.addClass("new_private_messages");
    function mid_animation() {
        li.removeClass("new_private_messages");
        li.addClass("new_private_messages_fadeout");
    }
    function end_animation() {
        li.removeClass("new_private_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

function animate_private_message_changes(new_private_message_count) {
    if (new_private_message_count > last_private_message_count) {
        do_new_private_messages_animation();
    }
    last_private_message_count = new_private_message_count;
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

    // integer counts
    exports.set_count("global", "private-message", counts.private_message_count);
    exports.set_count("global", "home", counts.home_unread_messages);

    // For now increases in private messages get special treatment in terms of 
    // animating the left pane.  It is unlikely that we will generalize this,
    // since Starred messages are user-initiated and Home messages would be too
    // spammy.
    animate_private_message_changes(counts.private_message_count);
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
            if (['private-message', 'starred'].indexOf(op_is[0]) !== -1) {
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
