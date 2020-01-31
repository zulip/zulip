const render_stream_privacy = require('../templates/stream_privacy.hbs');
const render_stream_sidebar_row = require('../templates/stream_sidebar_row.hbs');
const IntDict = require('./int_dict').IntDict;

let has_scrolled = false;

exports.update_count_in_dom = function (unread_count_elem, count) {
    const count_span = unread_count_elem.find('.count');
    const value_span = count_span.find('.value');

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
};


exports.stream_sidebar = (function () {
    const self = {};

    self.rows = new IntDict(); // stream id -> row widget

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

        self.rows.delete(stream_id);
    };

    return self;
}());

function get_search_term() {
    const search_box = $(".stream-list-filter");
    const search_term = search_box.expectOne().val().trim();
    return search_term;
}

exports.remove_sidebar_row = function (stream_id) {
    exports.stream_sidebar.remove_row(stream_id);
    exports.build_stream_list();
    exports.stream_cursor.redraw();
};

exports.create_initial_sidebar_rows = function () {
    // This code is slightly opaque, but it ends up building
    // up list items and attaching them to the "sub" data
    // structures that are kept in stream_data.js.
    const subs = stream_data.subscribed_subs();

    _.each(subs, function (sub) {
        exports.create_sidebar_row(sub);
    });
};

exports.build_stream_list = function () {
    // This function assumes we have already created the individual
    // sidebar rows.  Our job here is to build the bigger widget,
    // which largely is a matter of arranging the individual rows in
    // the right order.
    const streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    // The main logic to build the list is in stream_sort.js, and
    // we get three lists of streams (pinned/normal/dormant).
    const stream_groups = stream_sort.sort_groups(streams, get_search_term());

    if (stream_groups.same_as_before) {
        return;
    }

    const parent = $('#stream_filters');
    const elems = [];

    function add_sidebar_li(stream) {
        const sub = stream_data.get_sub(stream);
        const sidebar_row = exports.stream_sidebar.get_row(sub.stream_id);
        sidebar_row.update_whether_active();
        elems.push(sidebar_row.get_li());
    }

    parent.empty();

    _.each(stream_groups.pinned_streams, add_sidebar_li);

    const any_pinned_streams = stream_groups.pinned_streams.length > 0;
    const any_normal_streams = stream_groups.normal_streams.length > 0;
    const any_dormant_streams = stream_groups.dormant_streams.length > 0;

    if (any_pinned_streams && (any_normal_streams || any_dormant_streams)) {
        elems.push('<hr class="stream-split">');
    }

    _.each(stream_groups.normal_streams, add_sidebar_li);

    if (any_dormant_streams && any_normal_streams) {
        elems.push('<hr class="stream-split">');
    }

    _.each(stream_groups.dormant_streams, add_sidebar_li);

    parent.append(elems);
};

exports.get_stream_li = function (stream_id) {
    const row = exports.stream_sidebar.get_row(stream_id);
    if (!row) {
        // Not all streams are in the sidebar, so we don't report
        // an error here, and it's up for the caller to error if
        // they expected otherwise.
        return;
    }

    const li = row.get_li();
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

function stream_id_for_elt(elt) {
    return parseInt(elt.attr('data-stream-id'), 10);
}

exports.zoom_in_topics = function (options) {
    // This only does stream-related tasks related to zooming
    // in to more topics, which is basically hiding all the
    // other streams.

    $("#streams_list").expectOne().removeClass("zoom-out").addClass("zoom-in");

    // Hide stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).hide();
    });
    $(".stream-split").each(function () {
        $(this).hide();
    });

    $("#stream_filters li.narrow-filter").each(function () {
        const elt = $(this);
        const stream_id = options.stream_id;

        if (stream_id_for_elt(elt) === stream_id) {
            elt.show();
        } else {
            elt.hide();
        }
    });
};

exports.zoom_out_topics = function () {
    // Show stream list titles and pinned stream splitter
    $(".stream-filters-label").each(function () {
        $(this).show();
    });
    $(".stream-split").each(function () {
        $(this).show();
    });

    $("#streams_list").expectOne().removeClass("zoom-in").addClass("zoom-out");
    $("#stream_filters li.narrow-filter").show();
};

exports.set_in_home_view = function (stream_id, in_home) {
    const li = exports.get_stream_li(stream_id);
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
    const name = sub.name;
    const args = {
        name: name,
        id: sub.stream_id,
        uri: hash_util.by_stream_uri(sub.stream_id),
        is_muted: stream_data.is_muted(sub.stream_id) === true,
        invite_only: sub.invite_only,
        is_web_public: sub.is_web_public,
        color: sub.color,
        pin_to_top: sub.pin_to_top,
    };
    args.dark_background = stream_color.get_color_class(args.color);
    const list_item = $(render_stream_sidebar_row(args));
    return list_item;
}

function build_stream_sidebar_row(sub) {
    const self = {};
    const list_item = build_stream_sidebar_li(sub);

    self.update_whether_active = function () {
        if (stream_data.is_active(sub) || sub.pin_to_top === true) {
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
        const count = unread.num_unread_for_stream(sub.stream_id);
        exports.update_count_in_dom(list_item, count);
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

exports.redraw_stream_privacy = function (sub) {
    const li = exports.get_stream_li(sub.stream_id);
    if (!li) {
        // We don't want to raise error here, if we can't find stream in subscription
        // stream list. Cause we allow org admin to update stream privacy
        // even if they don't subscribe to public stream.
        return;
    }

    const div = li.find('.stream-privacy');
    const dark_background = stream_color.get_color_class(sub.color);

    const args = {
        invite_only: sub.invite_only,
        dark_background: dark_background,
    };

    const html = render_stream_privacy(args);
    div.html(html);
};

function set_stream_unread_count(stream_id, count) {
    const unread_count_elem = exports.get_stream_li(stream_id);
    if (!unread_count_elem) {
        // This can happen for legitimate reasons, but we warn
        // just in case.
        blueslip.warn('stream id no longer in sidebar: ' + stream_id);
        return;
    }
    exports.update_count_in_dom(unread_count_elem, count);
}

exports.update_streams_sidebar = function () {
    const finish = blueslip.start_timing('build_stream_list');
    exports.build_stream_list();
    finish();
    exports.stream_cursor.redraw();

    if (!narrow_state.active()) {
        return;
    }

    const filter = narrow_state.filter();

    exports.update_stream_sidebar_for_narrow(filter);
};

exports.update_dom_with_unread_counts = function (counts) {
    // counts.stream_count maps streams to counts
    for (const [stream_id, count] of counts.stream_count) {
        set_stream_unread_count(stream_id, count);
    }
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
        const stream_li = exports.get_stream_li(sub.stream_id);
        if (!stream_li) {
            blueslip.error('passed in bad stream id ' + sub.stream_id);
            return;
        }
        exports.scroll_stream_into_view(stream_li);
    }
};

exports.get_sidebar_stream_topic_info  = function (filter) {
    const result = {
        stream_id: undefined,
        topic_selected: false,
    };

    const op_stream = filter.operands('stream');
    if (op_stream.length === 0) {
        return result;
    }

    const stream_name = op_stream[0];
    const stream_id = stream_data.get_stream_id(stream_name);

    if (!stream_id) {
        return result;
    }

    if (!stream_data.id_is_subscribed(stream_id)) {
        return result;
    }

    result.stream_id = stream_id;

    const op_topic = filter.operands('topic');
    result.topic_selected = op_topic.length === 1;

    return result;
};

function deselect_stream_items() {
    $("ul#stream_filters li").removeClass('active-filter');
}

exports.update_stream_sidebar_for_narrow = function (filter) {
    const info = exports.get_sidebar_stream_topic_info(filter);

    deselect_stream_items();

    const stream_id = info.stream_id;

    if (!stream_id) {
        topic_zoom.clear_topics();
        return;
    }

    const stream_li = exports.get_stream_li(stream_id);

    if (!stream_li) {
        // It should be the case then when we have a subscribed
        // stream, there will always be a stream list item
        // corresponding to that stream in our sidebar.  We have
        // evidence that this assumption breaks down for some users,
        // but we are not clear why it happens.
        blueslip.error('No stream_li for subscribed stream ' + stream_id);
        topic_zoom.clear_topics();
        return;
    }

    if (!info.topic_selected) {
        stream_li.addClass('active-filter');
    }

    if (stream_id !== topic_list.active_stream_id()) {
        topic_zoom.clear_topics();
    }

    topic_list.rebuild(stream_li, stream_id);

    return stream_li;
};

exports.handle_narrow_activated = function (filter) {
    const stream_li = exports.update_stream_sidebar_for_narrow(filter);
    if (stream_li) {
        exports.scroll_stream_into_view(stream_li);
    }
};

exports.handle_narrow_deactivated = function () {
    deselect_stream_items();
    topic_zoom.clear_topics();
};

function focus_stream_filter(e) {
    exports.stream_cursor.reset();
    e.stopPropagation();
}

function keydown_enter_key() {
    const stream_id = exports.stream_cursor.get_key();

    if (stream_id === undefined) {
        // This can happen for empty searches, no need to warn.
        return;
    }

    const sub = stream_data.get_sub_by_id(stream_id);

    if (sub === undefined) {
        blueslip.error('Unknown stream_id for search/enter: ' + stream_id);
        return;
    }

    exports.clear_and_hide_search();
    narrow.by('stream', sub.name, {trigger: 'sidebar enter key'});
}

function actually_update_streams_for_search() {
    exports.update_streams_sidebar();
    resize.resize_page_components();
    exports.stream_cursor.reset();
}

const update_streams_for_search = _.throttle(actually_update_streams_for_search, 50);

exports.initialize = function () {
    exports.create_initial_sidebar_rows();

    // We build the stream_list now.  It may get re-built again very shortly
    // when new messages come in, but it's fairly quick.
    exports.build_stream_list();
    exports.set_event_handlers();
};

exports.set_event_handlers = function () {
    $(document).on('subscription_add_done.zulip', function (event) {
        exports.create_sidebar_row(event.sub);
        exports.build_stream_list();
        exports.stream_cursor.redraw();
    });

    $(document).on('subscription_remove_done.zulip', function (event) {
        exports.remove_sidebar_row(event.sub.stream_id);
    });


    $('#stream_filters').on('click', 'li .subscription_block', function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        const stream_id = stream_id_for_elt($(e.target).parents('li'));
        const sub = stream_data.get_sub_by_id(stream_id);
        popovers.hide_all();
        narrow.by('stream', sub.name, {trigger: 'sidebar'});

        exports.clear_and_hide_search();

        e.preventDefault();
        e.stopPropagation();
    });

    $('#clear_search_stream_button').on('click', exports.clear_search);

    $("#streams_header").expectOne().click(function (e) {
        exports.toggle_filter_displayed(e);
    });

    // check for user scrolls on streams list for first time
    ui.get_scroll_element($('#stream-filters-container')).on('scroll', function () {
        has_scrolled = true;
        // remove listener once user has scrolled
        $(this).off('scroll');
    });

    exports.stream_cursor = list_cursor({
        list: {
            scroll_container_sel: '#stream-filters-container',
            find_li: function (opts) {
                const stream_id = opts.key;
                const li = exports.get_stream_li(stream_id);
                return li;
            },
            first_key: stream_sort.first_stream_id,
            prev_key: stream_sort.prev_stream_id,
            next_key: stream_sort.next_stream_id,
        },
        highlight_class: 'highlighted_stream',
    });

    const $search_input = $('.stream-list-filter').expectOne();

    keydown_util.handle({
        elem: $search_input,
        handlers: {
            enter_key: function () {
                keydown_enter_key();
                return true;
            },
            up_arrow: function () {
                exports.stream_cursor.prev();
                return true;
            },
            down_arrow: function () {
                exports.stream_cursor.next();
                return true;
            },
        },
    });

    $search_input.on('click', focus_stream_filter);
    $search_input.on('focusout', exports.stream_cursor.clear);
    $search_input.on('input', update_streams_for_search);
};

exports.searching = function () {
    return $('.stream-list-filter').expectOne().is(':focus');
};

exports.escape_search = function () {
    const filter = $('.stream-list-filter').expectOne();
    if (filter.val() === '') {
        exports.clear_and_hide_search();
        return;
    }
    filter.val('');
    update_streams_for_search();
};

exports.clear_search = function (e) {
    e.stopPropagation();
    const filter = $('.stream-list-filter').expectOne();
    if (filter.val() === '') {
        exports.clear_and_hide_search();
        return;
    }
    filter.val('');
    filter.blur();
    update_streams_for_search();
};

exports.show_search_section = function () {
    $('.stream_search_section').expectOne().removeClass('notdisplayed');
    resize.resize_stream_filters_container();
};

exports.hide_search_section = function () {
    $('.stream_search_section').expectOne().addClass('notdisplayed');
    resize.resize_stream_filters_container();
};

exports.initiate_search = function () {
    exports.show_search_section();

    const filter = $('.stream-list-filter').expectOne();

    if (!$(".app-main .column-left").hasClass("expanded")) {
        popovers.hide_all();
        stream_popover.show_streamlist_sidebar();
    }
    filter.focus();

    exports.stream_cursor.reset();
};

exports.clear_and_hide_search = function () {
    const filter = $('.stream-list-filter');
    if (filter.val() !== '') {
        filter.val('');
        update_streams_for_search();
    }
    exports.stream_cursor.clear();
    filter.blur();

    exports.hide_search_section();
};

exports.toggle_filter_displayed = function (e) {
    if ($('.stream_search_section.notdisplayed').length === 0) {
        exports.clear_and_hide_search();
    } else {
        exports.initiate_search();
    }
    e.preventDefault();
};

exports.scroll_stream_into_view = function (stream_li) {
    const container = $('#stream-filters-container');

    if (stream_li.length !== 1) {
        blueslip.error('Invalid stream_li was passed in');
        return;
    }

    scroll_util.scroll_element_into_container(stream_li, container);
};

exports.maybe_scroll_narrow_into_view = function () {
    // we don't want to interfere with user scrolling once the page loads
    if (has_scrolled) {
        return;
    }

    const stream_li = exports.get_current_stream_li();
    if (stream_li) {
        exports.scroll_stream_into_view(stream_li);
    }
};

exports.get_current_stream_li = function () {
    const stream_id = topic_list.active_stream_id();

    if (!stream_id) {
        // stream_id is undefined in non-stream narrows
        return;
    }

    const stream_li = exports.get_stream_li(stream_id);

    if (!stream_li) {
        // This code path shouldn't ever be reached.
        blueslip.warn('No active stream_li found for defined id ' + stream_id);
        return;
    }

    return stream_li;
};

window.stream_list = exports;
