var stream_list = (function () {

var exports = {};

var zoomed_stream = '';
var previous_sort_order;
var previous_unpinned_order;

function filter_streams_by_search(streams) {
    var search_box = $(".stream-list-filter");

    var search_term = search_box.expectOne().val().trim();

    if (search_term === '') {
        return streams;
    }

    var search_terms = search_term.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var filtered_streams = _.filter(streams, function (stream) {
        return _.any(search_terms, function (search_term) {
            var lower_stream_name = stream.toLowerCase().split(" ");
            return _.any(lower_stream_name, function (name) {
                return name.indexOf(search_term) === 0;
            });
        });
    });

    return filtered_streams;
}

exports.stream_sidebar = (function () {
    var self = {};

    self.rows = new Dict(); // stream id -> row widget

    self.set_row = function (stream_id, widget) {
        self.rows.set(stream_id, widget);
    };

    self.get_row = function (stream_id) {
        return self.rows.get(stream_id);
    };

    self.has_row_for = function (stream_id) {
        return self.rows.has(stream_id);
    };

    self.remove_row = function (stream_id) {
        var widget = self.rows.get(stream_id);
        if (!widget) {
            blueslip.warn('Cannot remove stream id ' + stream_id);
            return;
        }
        widget.remove();
        self.rows.del(stream_id);
    };

    return self;
}());

exports.create_initial_sidebar_rows = function () {
    // This code is slightly opaque, but it ends up building
    // up list items and attaching them to the "sub" data
    // structures that are kept in stream_data.js.
    var subs = stream_data.subscribed_subs();

    _.each(subs, function (sub) {
        exports.create_sidebar_row(sub);
    });
};

exports.build_stream_list = function () {
    // This function assumes we have already created the individual
    // sidebar rows.  Our job here is to build the bigger widget,
    // which largely is a matter of arranging the individual rows in
    // the right order.
    var streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    streams = filter_streams_by_search(streams);

    var sort_recent = (streams.length > 40);
    var pinned_streams = [];
    var unpinned_streams = [];
    var parent = $('#stream_filters');
    var elems = [];

    function add_sidebar_li(stream) {
        var sub = stream_data.get_sub(stream);
        var sidebar_row = exports.stream_sidebar.get_row(sub.stream_id);
        if (sort_recent) {
            sidebar_row.update_whether_active();
        }
        elems.push(sidebar_row.get_li().get(0));
    }

    _.each(streams, function (stream) {
        var pinned = stream_data.get_sub(stream).pin_to_top;
        if (pinned) {
            pinned_streams.push(stream);
        } else {
            unpinned_streams.push(stream);
        }
    });

    unpinned_streams.sort(function (a, b) {
        if (sort_recent) {
            if (stream_data.is_active(b) && ! stream_data.is_active(a)) {
                return 1;
            } else if (! stream_data.is_active(b) && stream_data.is_active(a)) {
                return -1;
            }
        }
        return util.strcmp(a, b);
    });

    streams = pinned_streams.concat(unpinned_streams);

    if (previous_sort_order !== undefined &&
        util.array_compare(previous_sort_order, streams) &&
        util.array_compare(previous_unpinned_order, unpinned_streams)) {
        return;
    }
    previous_sort_order = streams;
    previous_unpinned_order = unpinned_streams;
    parent.empty();

    if (pinned_streams.length > 0) {
        _.each(pinned_streams, add_sidebar_li);
        elems.push($('<hr class="pinned-stream-split">').get(0));
    }
    if (unpinned_streams.length > 0) {
        _.each(unpinned_streams, add_sidebar_li);
    }

    $(elems).appendTo(parent);
};

function iterate_to_find(selector, name_to_find, context) {
    var lowercase_name = name_to_find.toLowerCase();
    var found = _.find($(selector, context), function (elem) {
        return $(elem).attr('data-name').toLowerCase() === lowercase_name;
    });
    return found ? $(found) : $();
}

function get_filter_li(type, name) {
    if (type === 'stream') {
        var sub = stream_data.get_sub(name);
        return $("#stream_sidebar_" + sub.stream_id);
    }
    return iterate_to_find("#" + type + "_filters > li", name);
}

function zoom_in() {
    popovers.hide_all();
    topic_list.zoom_in();
    $("#streams_list").expectOne().removeClass("zoom-out").addClass("zoom-in");
    zoomed_stream = narrow.stream();

    // Hide stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).hide();
    });
    $(".pinned-stream-split").each(function () {
        $(this).hide();
    });

    $("#stream_filters li.narrow-filter").each(function () {
        var elt = $(this);

        if (elt.attr('data-name') === zoomed_stream) {
            elt.show();
        } else {
            elt.hide();
        }
    });
}

function zoom_out(options) {
    popovers.hide_all();
    topic_list.zoom_out(options);

    // Show stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).show();
    });
    $(".pinned-stream-split").each(function () {
        $(this).show();
    });

    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").show();
}

function reset_to_unnarrowed(narrowed_within_same_stream) {
    if (topic_list.is_zoomed() && narrowed_within_same_stream !== true) {
        zoom_out({clear_topics: true});
    } else {
        topic_list.remove_expanded_topics();
    }
}

exports.set_in_home_view = function (stream, in_home) {
    var li = get_filter_li('stream', stream);
    if (in_home) {
        li.removeClass("out_of_home_view");
    } else {
        li.addClass("out_of_home_view");
    }
};

function build_stream_sidebar_li(sub) {
    var name = sub.name;
    var args = {name: name,
                id: sub.stream_id,
                uri: narrow.by_stream_uri(name),
                not_in_home_view: (stream_data.in_home_view(name) === false),
                invite_only: sub.invite_only,
                color: stream_data.get_color(name),
                pin_to_top: sub.pin_to_top
               };
    args.dark_background = stream_color.get_color_class(args.color);
    var list_item = $(templates.render('stream_sidebar_row', args));
    return list_item;
}

function build_stream_sidebar_row(sub) {
    var self = {};
    var list_item = build_stream_sidebar_li(sub);
    var stream_name = sub.name;

    self.update_whether_active = function () {
        if (stream_data.is_active(stream_name)) {
            list_item.removeClass('inactive_stream');
        } else {
            list_item.addClass('inactive_stream');
        }
    };

    self.get_li = function () {
        return list_item;
    };

    self.remove = function () {
        list_item.remove();
    };

    exports.stream_sidebar.set_row(sub.stream_id, self);
}

exports.create_sidebar_row = function (sub) {
    if (exports.stream_sidebar.has_row_for(sub.stream_id)) {
        // already exists
        blueslip.warn('Dup try to build sidebar row for stream ' + sub.stream_id);
        return;
    }
    build_stream_sidebar_row(sub);
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

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        if (count_span.parent().hasClass("subscription_block")) {
            count_span.parent(".subscription_block").removeClass("stream-with-count");
        }
        value_span.text('');
        return;
    }

    count_span.show();

    if (count_span.parent().hasClass("subscription_block")) {
        count_span.parent(".subscription_block").addClass("stream-with-count");
    }
    value_span.text(count);
}

function set_count(type, name, count) {
    var count_span = get_filter_li(type, name).find('.count');
    var value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
}

function rebuild_recent_topics(stream) {
    // TODO: Call rebuild_recent_topics less, not on every new
    // message.
    var stream_li = get_filter_li('stream', stream);
    topic_list.rebuild(stream_li, stream);
}

exports.update_streams_sidebar = function () {
    exports.build_stream_list();

    if (! narrow.active()) {
        return;
    }

    var op_stream = narrow.filter().operands('stream');
    if (op_stream.length !== 0) {
        if (stream_data.is_subscribed(op_stream[0])) {
            rebuild_recent_topics(op_stream[0]);
        }
    }
};

exports.update_dom_with_unread_counts = function (counts) {
    // We currently handle these message categories:
    //    home, starred, mentioned, streams, and topics
    //
    // Note that similar methods elsewhere in the code update
    // the "Private Message" section in the upper left corner
    // and the buddy lists in the right sidebar.

    // counts.stream_count maps streams to counts
    counts.stream_count.each(function (count, stream) {
        set_count("stream", stream, count);
    });

    // counts.subject_count maps streams to hashes of topics to counts
    counts.subject_count.each(function (subject_hash, stream) {
        subject_hash.each(function (count, subject) {
            topic_list.set_count(stream, subject, count);
        });
    });

    // integer counts
    set_count("global", "mentioned", counts.mentioned_message_count);
    set_count("global", "home", counts.home_unread_messages);

    unread_ui.set_count_toggle_button($("#streamlist-toggle-unreadcount"),
                                      counts.home_unread_messages);

    unread_ui.animate_mention_changes(get_filter_li('global', 'mentioned'),
                                      counts.mentioned_message_count);
};

exports.rename_stream = function (sub) {
    // The sub object is expected to already have the updated name
    build_stream_sidebar_row(sub);
    exports.build_stream_list(); // big hammer
};

exports.refresh_pinned_or_unpinned_stream = function (sub) {
    // Pinned/unpinned streams require re-ordering.
    // We use kind of brute force now, which is probably fine.
    build_stream_sidebar_row(sub);
    exports.update_streams_sidebar();
};

$(function () {
    // TODO, Eventually topic_list won't be a big singleton,
    // and we can create more component-based click handlers for
    // each stream.
    topic_list.set_click_handlers({
        zoom_in: zoom_in,
        zoom_out: zoom_out
    });

    pm_list.set_click_handlers();

    $(document).on('narrow_activated.zulip', function (event) {
        reset_to_unnarrowed(narrow.stream() === zoomed_stream);

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
            pm_list.expand(op_pm);
        } else {
            pm_list.close();
        }

        var op_stream = event.filter.operands('stream');
        if (op_stream.length !== 0 && stream_data.is_subscribed(op_stream[0])) {
            var stream_li = get_filter_li('stream', op_stream[0]);
            var op_subject = event.filter.operands('topic');
            if (op_subject.length === 0) {
                stream_li.addClass('active-filter');
            }
            rebuild_recent_topics(op_stream[0]);
            unread.process_visible();
        }
    });

    $(document).on('narrow_deactivated.zulip', function () {
        reset_to_unnarrowed();
        pm_list.close();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('subscription_add_done.zulip', function (event) {
        exports.create_sidebar_row(event.sub);
        exports.build_stream_list();
    });

    $(document).on('subscription_remove_done.zulip', function (event) {
        exports.stream_sidebar.remove_row(event.sub.stream_id);
        // We need to make sure we resort if the removed sub gets added again
        previous_sort_order = undefined;
        previous_unpinned_order = undefined;
    });

    $('#stream_filters').on('click', 'li .subscription_block', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if (ui.home_tab_obscured()) {
            ui.change_tab_to('#home');
        }
        var stream = $(e.target).parents('li').attr('data-name');
        popovers.hide_all();
        narrow.by('stream', stream, {select_first_unread: true, trigger: 'sidebar'});

        e.preventDefault();
        e.stopPropagation();
    });

});

function actually_update_streams_for_search() {
    exports.update_streams_sidebar();
    resize.resize_page_components();
}

var update_streams_for_search = _.throttle(actually_update_streams_for_search, 50);

exports.searching = function () {
    return $('.stream-list-filter').expectOne().is(':focus');
};

exports.escape_search = function () {
    var filter = $('.stream-list-filter').expectOne();
    if (filter.val() === '') {
        exports.clear_and_hide_search();
        return;
    }
    filter.val('');
    update_streams_for_search();
};

exports.initiate_search = function () {
    var filter = $('.stream-list-filter').expectOne();
    filter.removeClass('notdisplayed');
    filter.focus();
};

exports.clear_and_hide_search = function () {
    var filter = $('.stream-list-filter');
    if (filter.val() !== '') {
        filter.val('');
        update_streams_for_search();
    }
    filter.blur();
    filter.addClass('notdisplayed');
};

function focus_stream_filter(e) {
    e.stopPropagation();
}

function maybe_select_stream(e) {
    if (e.keyCode === 13) {
        // Enter key was pressed

        var topStream = $('#stream_filters li.narrow-filter').first().data('name');
        if (topStream !== undefined) {
            // undefined if there are no results
            if (ui.home_tab_obscured()) {
                ui.change_tab_to('#home');
            }
            exports.clear_and_hide_search();
            narrow.by('stream', topStream, {select_first_unread: true, trigger: 'sidebar enter key'});
            e.preventDefault();
            e.stopPropagation();
        }
    }
}

function toggle_filter_displayed(e) {
    if (e.target.id === 'streams_inline_cog') {
        return;
    }
    if ($('.stream-list-filter.notdisplayed').length === 0) {
        exports.clear_and_hide_search();
    } else {
        exports.initiate_search();
    }
    e.preventDefault();
}

$(function () {
    $(".stream-list-filter").expectOne()
        .on('click', focus_stream_filter)
        .on('input', update_streams_for_search)
        .on('keydown', maybe_select_stream);
});

$(function () {
    $("#streams_header").expectOne()
        .on('click', toggle_filter_displayed);
});

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = stream_list;
}
