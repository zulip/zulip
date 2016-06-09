var stream_list = (function () {

var exports = {};

var zoomed_to_topics = false;
var zoomed_stream = '';
var private_messages_open = false;
var last_private_message_count = 0;
var last_mention_count = 0;
var previous_sort_order;

function active_stream_name() {
    if (narrow.active()) {
        var op_streams = narrow.filter().operands('stream');
        if (op_streams) {
            return op_streams[0];
        }
    }
    return false;
}

exports.build_stream_list = function () {
    var streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    var sort_recent = (streams.length > 40);

    streams.sort(function (a, b) {
        if (sort_recent) {
            if (stream_data.recent_subjects.has(b) && ! stream_data.recent_subjects.has(a)) {
                return 1;
            } else if (! stream_data.recent_subjects.has(b) && stream_data.recent_subjects.has(a)) {
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
            if (! stream_data.recent_subjects.has(stream)) {
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
        var sub = stream_data.get_sub(name);
        return $("#stream_sidebar_" + sub.stream_id);
    } else if (type === "private") {
        if (name.indexOf(",") < 0) {
            return $("li.user_sidebar_entry[data-email='" + name + "']");
        } else {
            return $("li.group-pms-sidebar-entry[data-emails='" + name + "']");
        }
    }
    return iterate_to_find("#" + type + "_filters > li", name);
}

function zoom_in() {
    popovers.hide_all();
    zoomed_to_topics = true;
    $("#streams_list").expectOne().removeClass("zoom-out").addClass("zoom-in");
    zoomed_stream = active_stream_name();

    $("#stream_filters li.narrow-filter").each(function () {
        var elt = $(this);

        if (elt.attr('data-name') === zoomed_stream) {
            elt.show();
        } else {
            elt.hide();
        }
    });
}

function zoom_out() {
    popovers.hide_all();
    zoomed_to_topics = false;
    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").show();
}

function remove_expanded_subjects() {
    popovers.hide_topic_sidebar_popover();
    $("ul.expanded_subjects").remove();
}

function remove_expanded_private_messages() {
    popovers.hide_topic_sidebar_popover();
    $("ul.expanded_private_messages").remove();
    resize.resize_stream_filters_container();
}

function reset_to_unnarrowed(narrowed_within_same_stream) {
    if (zoomed_to_topics && narrowed_within_same_stream !== true) {
        zoom_out();
    }

    private_messages_open = false;
    $("ul.filters li").removeClass('active-filter active-sub-filter');
    remove_expanded_subjects();
    remove_expanded_private_messages();
}

function get_subject_filter_li(stream, subject) {
    var stream_li = get_filter_li('stream', stream);
    return iterate_to_find(".expanded_subjects li.expanded_subject", subject, stream_li);
}

function get_private_message_filter_li(conversation) {
    var pm_li = get_filter_li('global', 'private');
    return iterate_to_find(".expanded_private_messages li.expanded_private_message",
        conversation, pm_li);
}

exports.set_in_home_view = function (stream, in_home) {
    var li = get_filter_li('stream', stream);
    if (in_home) {
        li.removeClass("out_of_home_view");
    } else {
        li.addClass("out_of_home_view");
    }
};

function build_stream_sidebar_row(name) {
    var sub = stream_data.get_sub(name);
    var args = {name: name,
                id: sub.stream_id,
                uri: narrow.by_stream_uri(name),
                not_in_home_view: (stream_data.in_home_view(name) === false),
                invite_only: sub.invite_only,
                color: stream_data.get_color(name)
               };
    args.dark_background = stream_color.get_color_class(args.color);
    var list_item = $(templates.render('stream_sidebar_row', args));
    $("#stream_filters").append(list_item);
    return list_item;
}

exports.add_stream_to_sidebar = function (stream_name) {
    if (exports.get_stream_li(stream_name).length) {
        // already exists
        return false;
    }
    return build_stream_sidebar_row(stream_name);
};

exports.redraw_stream_privacy = function (stream_name) {
    var li = exports.get_stream_li(stream_name);
    var div = li.find('.stream-privacy');
    var swatch = li.find('.streamlist_swatch');
    var sub = stream_data.get_sub(stream_name);
    var color = stream_data.get_color(stream_name);
    var dark_background = stream_color.get_color_class(color);

    var args = {
        invite_only: sub.invite_only,
        dark_background: dark_background
    };

    if (sub.invite_only) {
        swatch.addClass("private-stream-swatch");
    } else {
        swatch.removeClass("private-stream-swatch");
    }

    var html = templates.render('stream_privacy', args);
    div.html(html);
};

exports.get_stream_li = function (stream_name) {
    return get_filter_li('stream', stream_name);
};

exports.get_count = function (type, name) {
    return get_filter_li(type, name).find('.count .value').text();
};

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        if (count_span.parent().hasClass("subscription_block")) {
            count_span.parent(".subscription_block").removeClass("stream-with-count");
        } else if (count_span.parent().hasClass("user_sidebar_entry")) {
            count_span.parent(".user_sidebar_entry").removeClass("user-with-count");
        } else if (count_span.parent().hasClass("group-pms-sidebar-entry")) {
            count_span.parent(".group-pms-sidebar-entry").removeClass("group-with-count");
        }
        value_span.text('');
        return;
    }

    count_span.show();

    if (count_span.parent().hasClass("subscription_block")) {
        count_span.parent(".subscription_block").addClass("stream-with-count");
    } else if (count_span.parent().hasClass("user_sidebar_entry")) {
        count_span.parent(".user_sidebar_entry").addClass("user-with-count");
    } else if (count_span.parent().hasClass("group-pms-sidebar-entry")) {
            count_span.parent(".group-pms-sidebar-entry").addClass("group-with-count");
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


exports.set_pm_conversation_count = function (conversation, count) {
    var pm_li = get_private_message_filter_li(conversation);
    var count_span = pm_li.find('.private_message_count');
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

exports._build_subject_list = function (stream, active_topic, max_subjects) {
    var subjects = stream_data.recent_subjects.get(stream) || [];

    if (active_topic) {
        active_topic = active_topic.toLowerCase();
    }

    var display_subjects = [];
    var hiding_topics = false;

    _.each(subjects, function (subject_obj, idx) {
        var topic_name = subject_obj.subject;
        var num_unread = unread.num_unread_for_subject(stream, subject_obj.canon_subject);

        // Show the most recent subjects, as well as any with unread messages
        var always_visible = (idx < max_subjects) || (num_unread > 0) || (active_topic === topic_name);

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
        display_subjects.push(display_subject);
    });

    var topic_dom = templates.render('sidebar_subject_list',
                                      {subjects: display_subjects,
                                       want_show_more_topics_links: hiding_topics,
                                       stream: stream});

    return topic_dom;
};

exports._build_private_messages_list = function (active_conversation, max_private_messages) {

    var private_messages = message_store.recent_private_messages || [];
    var display_messages = [];
    var hiding_messages = false;

    _.each(private_messages, function (private_message_obj, idx) {
        var recipients_string = private_message_obj.display_reply_to;
        var replies_to = private_message_obj.reply_to;
        var num_unread = unread.num_unread_for_person(private_message_obj.reply_to);

        // Show the most recent subjects, as well as any with unread messages
        var always_visible = (idx < max_private_messages) || (num_unread > 0)
            || (replies_to === active_conversation);

        if (!always_visible) {
            hiding_messages = true;
        }

        var display_message = {
            recipients: recipients_string,
            reply_to: replies_to,
            unread: num_unread,
            is_zero: num_unread === 0,
            zoom_out_hide: !always_visible,
            url: narrow.pm_with_uri(private_message_obj.reply_to)
        };
        display_messages.push(display_message);
    });

    var recipients_dom = templates.render('sidebar_private_message_list',
                                  {messages: display_messages,
                                   want_show_more_messages_links: hiding_messages});
    return recipients_dom;
};

function rebuild_recent_subjects(stream, active_topic) {
    // TODO: Call rebuild_recent_subjects less, not on every new
    // message.
    remove_expanded_subjects();
    var max_subjects = 5;
    var stream_li = get_filter_li('stream', stream);

    var topic_dom = exports._build_subject_list(stream, active_topic, max_subjects);
    stream_li.append(topic_dom);

    if (active_topic) {
        get_subject_filter_li(stream, active_topic).addClass('active-sub-filter');
    }
}

function rebuild_recent_private_messages(active_conversation) {
    remove_expanded_private_messages();
    if (private_messages_open)
    {
        var max_private_messages = 5;
        var private_li = get_filter_li('global', 'private');
        var private_messages_dom = exports._build_private_messages_list(active_conversation,
            max_private_messages);
        private_li.append(private_messages_dom);
    }
    if (active_conversation) {
        get_private_message_filter_li(active_conversation).addClass('active-sub-filter');
    }

    resize.resize_stream_filters_container();
}

exports.update_streams_sidebar = function () {
    exports.build_stream_list();

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

exports.update_private_messages = function () {
    exports._build_private_messages_list();

    if (! narrow.active()) {
        return;
    }

    var is_pm_filter = _.contains(narrow.filter().operands('is'), "private");
    var conversation = narrow.filter().operands('pm-with');
    if (conversation.length === 1) {
        rebuild_recent_private_messages(conversation[0]);
    } else if (conversation.length !== 0) {
        // TODO: This should be the reply-to of the thread.
        rebuild_recent_private_messages("");
    } else if (is_pm_filter) {
        rebuild_recent_private_messages("");
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
        exports.set_pm_conversation_count(person, count);
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
    sub.sidebar_li = build_stream_sidebar_row(sub.name);
    exports.build_stream_list(); // big hammer
};

$(function () {
    $(document).on('narrow_activated.zulip', function (event) {
        reset_to_unnarrowed(active_stream_name() === zoomed_stream);

        // TODO: handle confused filters like "in:all stream:foo"
        var op_in = event.filter.operands('in');
        if (op_in.length !== 0) {
            if (['all', 'home'].indexOf(op_in[0]) !== -1) {
                $("#global_filters li[data-name='" + op_in[0] + "']").addClass('active-filter');
            }
        }
        var op_is = event.filter.operands('is');
        if (op_is.length !== 0) {
            if (['starred', 'mentioned'].indexOf(op_is[0]) !== -1) {
                $("#global_filters li[data-name='" + op_is[0] + "']").addClass('active-filter');
            }
        }

        var op_pm = event.filter.operands('pm-with');
        if ((op_is.length !== 0 && _.contains(op_is, "private")) || op_pm.length !== 0) {
            private_messages_open = true;
            if (op_pm.length === 1) {
                $("#user_presences li[data-email='" + op_pm[0] + "']").addClass('active-filter');
                rebuild_recent_private_messages(op_pm[0]);
            } else if (op_pm.length !== 0) {
                // TODO: Should pass the reply-to of the thread
                rebuild_recent_private_messages("");
            } else {
                $("#global_filters li[data-name='private']").addClass('active-filter zoom-out');
                rebuild_recent_private_messages("");
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
            unread.process_visible();
        }
    });

    $(document).on('narrow_deactivated.zulip', function (event) {
        reset_to_unnarrowed();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('sub_obj_created.zulip', function (event) {
        if (event.sub.subscribed) {
            var stream_name = event.sub.name;
            var li = exports.add_stream_to_sidebar(stream_name);
            if (li) {
                event.sub.sidebar_li = li;
            }
        }
    });

    $(document).on('subscription_add_done.zulip', function (event) {
        var stream_name = event.sub.name;
        var li = exports.add_stream_to_sidebar(stream_name);
        if (li) {
            event.sub.sidebar_li = li;
        }
        exports.build_stream_list();
    });

    $(document).on('subscription_remove_done.zulip', function (event) {
        var stream_name = event.sub.name;
        exports.remove_narrow_filter(stream_name, 'stream');
        // We need to make sure we resort if the removed sub gets added again
        previous_sort_order = undefined;
    });

    $('.show-all-streams').on('click', function (e) {
        zoom_out();
        e.preventDefault();
        e.stopPropagation();
    });

    $('#stream_filters').on('click', '.show-more-topics', function (e) {
        var stream = $(e.target).parents('.show-more-topics').attr('data-name');

        zoom_in();

        e.preventDefault();
        e.stopPropagation();
    });

    $('#global_filters').on('click', '.show-more-private-messages', function (e) {
        popovers.hide_all();
        $(".expanded_private_messages").expectOne().removeClass("zoom-out").addClass("zoom-in");
        $(".expanded_private_messages li.expanded_private_message").each(function () {
            $(this).show();
        });

        e.preventDefault();
        e.stopPropagation();
    });

    $('#stream_filters').on('click', 'li .subscription_block', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if (ui.home_tab_obscured()) {
            ui.change_tab_to('#home');
        }
        var stream = $(e.target).parents('li').attr('data-name');

        narrow.by('stream', stream, {select_first_unread: true, trigger: 'sidebar'});

        e.preventDefault();
        e.stopPropagation();
    });

    $('#stream_filters').on('click', '.subject_box', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if (ui.home_tab_obscured()) {
            ui.change_tab_to('#home');
        }

        var stream = $(e.target).parents('ul').attr('data-stream');
        var subject = $(e.target).parents('li').attr('data-name');

        narrow.activate([{operator: 'stream',  operand: stream},
                         {operator: 'topic', operand: subject}],
                        {select_first_unread: true, trigger: 'sidebar'});

        e.preventDefault();
    });

});

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = stream_list;
}
