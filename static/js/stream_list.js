var stream_list = (function () {

var exports = {};

var zoomed_stream = '';

function update_count_in_dom(unread_count_elem, count) {
    var count_span = unread_count_elem.find('.count');
    var value_span = count_span.find('.value');

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
        // This only removes the row from our data structure.
        // Our caller should use build_stream_list() to re-draw
        // the sidebar, so that we don't have to deal with edge
        // cases like removing the last pinned stream (and removing
        // the divider).

        self.rows.del(stream_id);
    };

    return self;
}());

function get_search_term() {
    var search_box = $(".stream-list-filter");
    var search_term = search_box.expectOne().val().trim();
    return search_term;
}

exports.remove_sidebar_row = function (stream_id) {
    exports.stream_sidebar.remove_row(stream_id);
    exports.build_stream_list();
};

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

    // The main logic to build the list is in stream_sort.js, and
    // we get three lists of streams (pinned/normal/dormant).
    var stream_groups = stream_sort.sort_groups(get_search_term());

    if (stream_groups.same_as_before) {
        return;
    }

    var parent = $('#stream_filters');
    var elems = [];

    function add_sidebar_li(stream) {
        var sub = stream_data.get_sub(stream);
        var sidebar_row = exports.stream_sidebar.get_row(sub.stream_id);
        sidebar_row.update_whether_active();
        elems.push(sidebar_row.get_li().get(0));
    }

    parent.empty();

    _.each(stream_groups.pinned_streams, add_sidebar_li);

    if (stream_groups.pinned_streams.length > 0) {
        elems.push($('<hr class="stream-split">').get(0));
    }

    _.each(stream_groups.normal_streams, add_sidebar_li);

    if (stream_groups.dormant_streams.length > 0) {
        elems.push($('<hr class="stream-split">').get(0));
    }

    _.each(stream_groups.dormant_streams, add_sidebar_li);

    parent.append(elems);
};

function iterate_to_find(selector, name_to_find, context) {
    var lowercase_name = name_to_find.toLowerCase();
    var found = _.find($(selector, context), function (elem) {
        return $(elem).attr('data-name').toLowerCase() === lowercase_name;
    });
    return found ? $(found) : $();
}

function get_filter_li(type, name) {
    return iterate_to_find("#" + type + "_filters > li", name);
}

exports.get_stream_li = function (stream_id) {
    var row = exports.stream_sidebar.get_row(stream_id);
    if (!row) {
        // Not all streams are in the sidebar, so we don't report
        // an error here, and it's up for the caller to error if
        // they expected otherwise.
        return;
    }

    var li = row.get_li();
    if (!li) {
        blueslip.error('Cannot find li for id ' + stream_id);
        return;
    }

    if (li.length > 1) {
        blueslip.error('stream_li has too many elements for ' + stream_id);
        return;
    }

    return li;
};

function zoom_in() {
    popovers.hide_all();
    topic_list.zoom_in();
    $("#streams_list").expectOne().removeClass("zoom-out").addClass("zoom-in");
    zoomed_stream = narrow_state.stream();

    // Hide stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).hide();
    });
    $(".stream-split").each(function () {
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
    $(".stream-split").each(function () {
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

exports.set_in_home_view = function (stream_id, in_home) {
    var li = exports.get_stream_li(stream_id);
    if (!li) {
        blueslip.error('passed in bad stream id ' + stream_id);
        return;
    }

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
                not_in_home_view: (stream_data.in_home_view(sub.stream_id) === false),
                invite_only: sub.invite_only,
                color: stream_data.get_color(name),
                pin_to_top: sub.pin_to_top,
               };
    args.dark_background = stream_color.get_color_class(args.color);
    var list_item = $(templates.render('stream_sidebar_row', args));
    return list_item;
}

function build_stream_sidebar_row(sub) {
    var self = {};
    var list_item = build_stream_sidebar_li(sub);

    self.update_whether_active = function () {
        if (stream_data.is_active(sub)) {
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


    self.update_unread_count = function () {
        var count = unread.num_unread_for_stream(sub.stream_id);
        update_count_in_dom(list_item, count);
    };

    self.update_unread_count();

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
    var sub = stream_data.get_sub(stream_name);
    var li = exports.get_stream_li(sub.stream_id);
    if (!li) {
        blueslip.error('passed in bad stream: ' + stream_name);
        return;
    }

    var div = li.find('.stream-privacy');
    var color = stream_data.get_color(stream_name);
    var dark_background = stream_color.get_color_class(color);

    var args = {
        invite_only: sub.invite_only,
        dark_background: dark_background,
    };

    var html = templates.render('stream_privacy', args);
    div.html(html);
};

function set_count(type, name, count) {
    var unread_count_elem = get_filter_li(type, name);
    update_count_in_dom(unread_count_elem, count);
}

function set_stream_unread_count(stream_id, count) {
    var unread_count_elem = exports.get_stream_li(stream_id);
    if (!unread_count_elem) {
        // This can happen for legitimate reasons, but we warn
        // just in case.
        blueslip.warn('stream id no longer in sidebar: ' + stream_id);
        return;
    }
    update_count_in_dom(unread_count_elem, count);
}

function rebuild_recent_topics(stream_name) {
    // TODO: Call rebuild_recent_topics less, not on every new
    // message.
    var stream_id = stream_data.get_stream_id(stream_name);
    var stream_li = exports.get_stream_li(stream_id);
    topic_list.rebuild(stream_li, stream_id);
}

exports.update_streams_sidebar = function () {
    exports.build_stream_list();

    if (! narrow_state.active()) {
        return;
    }

    var filter = narrow_state.filter();

    exports.maybe_activate_stream_item(filter);
};

exports.update_dom_with_unread_counts = function (counts) {
    // We currently handle these message categories:
    //    home, starred, mentioned, streams, and topics
    //
    // Note that similar methods elsewhere in the code update
    // the "Private Message" section in the upper left corner
    // and the buddy lists in the right sidebar.

    // counts.stream_count maps streams to counts
    counts.stream_count.each(function (count, stream_id) {
        set_stream_unread_count(stream_id, count);
    });

    // counts.subject_count maps streams to hashes of topics to counts
    counts.subject_count.each(function (subject_hash, stream_id) {
        subject_hash.each(function (count, subject) {
            topic_list.set_count(stream_id, subject, count);
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
    exports.update_streams_sidebar(); // big hammer
};

exports.refresh_pinned_or_unpinned_stream = function (sub) {
    // Pinned/unpinned streams require re-ordering.
    // We use kind of brute force now, which is probably fine.
    build_stream_sidebar_row(sub);
    exports.update_streams_sidebar();

    // Only scroll pinned topics into view.  If we're unpinning
    // a topic, we may be literally trying to get it out of
    // our sight.
    if (sub.pin_to_top) {
        var stream_li = exports.get_stream_li(sub.stream_id);
        if (!stream_li) {
            blueslip.error('passed in bad stream id ' + sub.stream_id);
            return;
        }
        exports.scroll_to_active_stream(stream_li);
    }
};

exports.maybe_activate_stream_item = function (filter) {
    var op_stream = filter.operands('stream');
    if (op_stream.length !== 0) {
        var stream_name = op_stream[0];
        var stream_id = stream_data.get_stream_id(stream_name);

        if (stream_id && stream_data.id_is_subscribed(stream_id)) {
            var stream_li = exports.get_stream_li(stream_id);

            if (!stream_li) {
                // It should be the case then when we have a subscribed
                // stream, there will always be a stream list item
                // corresponding to that stream in our sidebar.  We have
                // evidence that this assumption breaks down for some users,
                // but we are not clear why it happens.
                blueslip.error('No stream_li for subscribed stream ' + stream_name);
                return;
            }

            var op_subject = filter.operands('topic');
            if (op_subject.length === 0) {
                stream_li.addClass('active-filter');
            }
            rebuild_recent_topics(stream_name);

            return stream_li;
        }
    }
};

function deselect_top_left_corner_items() {
    $("ul.filters li").removeClass('active-filter active-sub-filter');
}

exports.initialize = function () {
    // TODO, Eventually topic_list won't be a big singleton,
    // and we can create more component-based click handlers for
    // each stream.
    topic_list.set_click_handlers({
        zoom_in: zoom_in,
        zoom_out: zoom_out,
    });

    pm_list.set_click_handlers();

    $(document).on('narrow_activated.zulip', function (event) {
        deselect_top_left_corner_items();
        reset_to_unnarrowed(narrow_state.stream() === zoomed_stream);

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

        var stream_li = exports.maybe_activate_stream_item(event.filter);
        if (stream_li) {
            exports.scroll_to_active_stream(stream_li);
        }
    });

    $(document).on('narrow_deactivated.zulip', function () {
        deselect_top_left_corner_items();
        reset_to_unnarrowed();
        pm_list.close();
        $("#global_filters li[data-name='home']").addClass('active-filter');
    });

    $(document).on('subscription_add_done.zulip', function (event) {
        exports.create_sidebar_row(event.sub);
        exports.build_stream_list();
    });

    $(document).on('subscription_remove_done.zulip', function (event) {
        exports.remove_sidebar_row(event.sub.stream_id);
    });


    $('#stream_filters').on('click', 'li .subscription_block', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        if (overlays.is_active()) {
            ui_util.change_tab_to('#home');
        }
        var stream = $(e.target).parents('li').attr('data-name');
        popovers.hide_all();
        narrow.by('stream', stream, {select_first_unread: true, trigger: 'sidebar'});

        e.preventDefault();
        e.stopPropagation();
    });

};

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

exports.clear_search = function () {
    var filter = $('.stream-list-filter').expectOne();
    if (filter.val() === '') {
        exports.clear_and_hide_search();
        return;
    }
    filter.val('');
    filter.blur();
    update_streams_for_search();
};

exports.initiate_search = function () {
    var filter = $('.stream-list-filter').expectOne();
    filter.parent().removeClass('notdisplayed');
    filter.focus();
    $('#clear_search_stream_button').removeAttr('disabled');
};

exports.clear_and_hide_search = function () {
    var filter = $('.stream-list-filter');
    if (filter.val() !== '') {
        filter.val('');
        update_streams_for_search();
    }
    filter.blur();
    filter.parent().addClass('notdisplayed');
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
            if (overlays.is_active()) {
                ui_util.change_tab_to('#home');
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
    if ($('#stream-filters-container .input-append.notdisplayed').length === 0) {
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
    $('#clear_search_stream_button').on('click', exports.clear_search);
});

$(function () {
    $("#streams_header").expectOne()
        .on('click', toggle_filter_displayed);
});

exports.scroll_to_active_stream = function (stream_li) {
    var container = $('#stream-filters-container');

    if (stream_li.length !== 1) {
        blueslip.error('Invalid stream_li was passed in');
        return;
    }

    exports.scroll_element_into_container(stream_li, container);
};

exports.scroll_element_into_container = function (active_elem, container) {
    // This is a generic function to make active_elem visible in
    // container by scrolling container appropriately.  We may want to
    // eventually move this into another module, but I couldn't find
    // an ideal landing space for this.  I considered a few modules, but
    // some are already kind of bloated (ui.js), some may be deprecated
    // (scroll_bar.js), and some just aren't exact fits (resize.js).
    //
    // This does the minimum amount of scrolling that is needed to make
    // the element visible.  It doesn't try to center the element, so
    // this will be non-intrusive to users when they already have
    // the element visible.

    var active_top = active_elem.position().top;
    var delta = 0;

    if (active_top < 0) {
        delta = active_top;
    } else {
        var active_bottom = active_top + active_elem.height();
        var container_height = container.height();

        if (active_bottom > container_height) {
            delta = active_bottom - container_height;
        }
    }

    if (delta === 0) {
        return;
    }

    container.scrollTop(container.scrollTop() + delta);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = stream_list;
}
