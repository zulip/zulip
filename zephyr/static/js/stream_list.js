var stream_list = (function () {

var exports = {};

exports.sort_narrow_list = function () {
    var sort_recent = (subs.subscribed_streams().length > 40);
    var items = $('#stream_filters > li').get();
    var parent = $('#stream_filters');
    items.sort(function(a,b){
        var a_stream_name = $(a).attr('data-name');
        var b_stream_name = $(b).attr('data-name');
        if (sort_recent) {
            if (recent_subjects[b_stream_name] !== undefined &&
                recent_subjects[a_stream_name] === undefined) {
                return 1;
            } else if (recent_subjects[b_stream_name] === undefined &&
                       recent_subjects[a_stream_name] !== undefined) {
                return -1;
            }
        }
        return util.strcmp(a_stream_name, b_stream_name);
    });

    parent.empty();

    $.each(items, function(i, li){
        var stream_name = $(li).attr('data-name');
        if (sort_recent) {
            if (recent_subjects[stream_name] === undefined) {
                $(li).addClass("inactive_stream");
            } else {
                $(li).removeClass("inactive_stream");
            }
        }
        parent.append(li);
    });
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

function add_narrow_filter(name, type) {
    var uri = "#narrow/stream/" + hashchange.encodeHashComponent(name);
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
    list_item = $('<li>').attr('data-name', name).html(swatch);
    if (type === 'stream') {
        list_item.attr('id', "stream_sidebar_" + subs.stream_id(name));
    }

    list_item.append($('<a>').attr('href', uri)
                     .addClass('subscription_name')
                     .text(name)
                     .append('<span class="count">(<span class="value"></span>)</span>'));
    if (type === "stream" && subs.have(name).invite_only) {
        list_item.append("<i class='icon-lock'/>");
    }
    $("#" + type + "_filters").append(list_item);
}

exports.get_count = function (type, name) {
    return get_filter_li(type, name).find('.count .value').text();
};

exports.set_count = function (type, name, count) {
    var count_span = get_filter_li(type, name).find('.count');
    var value_span = count_span.find('.value');

    if (count === 0) {
        return exports.clear_count(type, name);
    }
    count_span.show();

    value_span.text(count);
};

exports.clear_count = function (type, name) {
    get_filter_li(type, name).find('.count').hide()
                                            .find('.value').text('');
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
    });

    $(document).on('narrow_deactivated.zephyr', function (event) {
        $("ul.filters li").removeClass('active-filter active-subject-filter');
        $("ul.expanded_subjects").remove();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('sub_obj_created.zephyr', function (event) {
        if (event.sub.subscribed) {
            var stream_name = event.sub.name;
            add_narrow_filter(stream_name, "stream");
        }
    });

    $(document).on('subscription_add_done.zephyr', function (event) {
        var stream_name = event.sub.name;
        add_narrow_filter(stream_name, "stream");
        exports.sort_narrow_list();
    });

    $(document).on('subscription_remove_done.zephyr', function (event) {
        var stream_name = event.sub.name;
        exports.remove_narrow_filter(stream_name, 'stream');
    });
});

return exports;
}());
