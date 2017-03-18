var stream_popover = (function () {

var exports = {};

// We handle stream popovers and topic popovers in this
// module.  Both are popped up from the left sidebar.
var current_stream_sidebar_elem;
var current_topic_sidebar_elem;

exports.stream_popped = function () {
    return current_stream_sidebar_elem !== undefined;
};

exports.topic_popped = function () {
    return current_topic_sidebar_elem !== undefined;
};

exports.hide_stream_popover = function () {
    if (exports.stream_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        current_stream_sidebar_elem = undefined;
    }
};

exports.hide_topic_popover = function () {
    if (exports.topic_popped()) {
        $(current_topic_sidebar_elem).popover("destroy");
        current_topic_sidebar_elem = undefined;
    }
};

// These are the only two functions that is really shared by the
// two popovers, so we could split out topic stuff to
// another module pretty easily.
exports.show_streamlist_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

exports.restore_stream_list_size = function () {
    $(".app-main .column-left").removeClass("expanded");
};


function stream_popover_sub(e) {
    // TODO: use data-stream-id in stream list
    var stream_name = $(e.currentTarget).parents('ul').attr('data-name');
    var sub = stream_data.get_sub(stream_name);
    if (!sub) {
        blueslip.error('Unknown stream: ' + stream_name);
        return;
    }
    return sub;
}

// This little function is a workaround for the fact that
// Bootstrap popovers don't properly handle being resized --
// so after resizing our popover to add in the spectrum color
// picker, we need to adjust its height accordingly.
function update_spectrum(popover, update_func) {
    var initial_height = popover[0].offsetHeight;

    var colorpicker = popover.find('.colorpicker-container').find('.colorpicker');
    update_func(colorpicker);
    var after_height = popover[0].offsetHeight;

    var popover_root = popover.closest(".popover");
    var current_top_px = parseFloat(popover_root.css('top').replace('px', ''));
    var height_delta = - (after_height - initial_height) * 0.5;

    popover_root.css('top', (current_top_px + height_delta) + "px");
}

function build_stream_popover(e) {
    var elt = e.target;
    if (exports.stream_popped()
        && current_stream_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_stream_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    var stream = $(elt).parents('li').attr('data-name');

    var content = templates.render(
        'stream_sidebar_actions',
        {stream: stream_data.get_sub(stream)}
    );

    $(elt).popover({
        content: content,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");
    var data_id = stream_data.get_sub(stream).stream_id;
    var popover = $('.streams_popover[data-id=' + data_id + ']');

    update_spectrum(popover, function (colorpicker) {
        colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options);
    });

    current_stream_sidebar_elem = elt;
    e.stopPropagation();
}

function build_topic_popover(e) {
    var elt = e.target;

    if (exports.topic_popped()
        && current_topic_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_topic_popover();
        e.stopPropagation();
        return;
    }

    var stream_name = $(elt).closest('.topic-list').expectOne().attr('data-stream');
    var topic_name = $(elt).closest('li').expectOne().attr('data-name');

    var sub = stream_data.get_sub(stream_name);
    if (!sub) {
        blueslip.error('cannot build topic popover for stream: ' + stream_name);
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    var is_muted = muting.is_topic_muted(stream_name, topic_name);
    var can_mute_topic = !is_muted;
    var can_unmute_topic = is_muted;

    var content = templates.render('topic_sidebar_actions', {
        stream_name: stream_name,
        stream_id: sub.stream_id,
        topic_name: topic_name,
        can_mute_topic: can_mute_topic,
        can_unmute_topic: can_unmute_topic,
    });

    $(elt).popover({
        content: content,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");

    current_topic_sidebar_elem = elt;
    e.stopPropagation();
}

exports.register_click_handlers = function () {
    $('#stream_filters').on('click',
        '.stream-sidebar-arrow', build_stream_popover);

    $('#stream_filters').on('click',
        '.topic-sidebar-arrow', build_topic_popover);

    exports.register_stream_handlers();
    exports.register_topic_handlers();
};

exports.register_stream_handlers = function () {
    // Stream settings
    $('body').on('click', '.open_stream_settings', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();

        window.location.hash = "#streams";
        // the template for subs needs to render.

        subs.onlaunch("narrow_to_row", function () {
            $(".stream-row[data-stream-name='" + sub.name + "']").click();
        }, true);
    });

    // Narrow to stream
    $('body').on('click', '.narrow_to_stream', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        narrow.by('stream', sub.name,
            {select_first_unread: true, trigger: 'sidebar popover'}
        );
        e.stopPropagation();
    });

    // Pin/unpin
    $('body').on('click', '.pin_to_top', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        subs.toggle_pin_to_top_stream(sub);
        e.stopPropagation();
    });

    // Compose a message to stream
    $('body').on('click', '.compose_to_stream', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        compose.start('stream', {stream: sub.name, trigger: 'sidebar stream actions'});
        e.stopPropagation();
    });

    // Mark all messages as read
    $('body').on('click', '.mark_stream_as_read', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        unread_ui.mark_stream_as_read(sub.name);
        e.stopPropagation();
    });

    // Mute/unmute
    $('body').on('click', '.toggle_home', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        subs.toggle_home(sub);
        e.stopPropagation();
    });

    // Unsubscribe
    $('body').on("click", ".popover_sub_unsub_button", function (e) {
        $(this).toggleClass("unsub");
        $(this).closest(".popover").fadeOut(500).delay(500).remove();

        var sub = stream_popover_sub(e);
        subs.sub_or_unsub(sub);
        e.preventDefault();
        e.stopPropagation();
    });

    // Choose custom color
    $('body').on('click', '.custom_color', function (e) {
        update_spectrum($(e.target).closest('.streams_popover'), function (colorpicker) {
            colorpicker.spectrum("destroy");
            colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options_full);
            // In theory this should clean up the old color picker,
            // but this seems a bit flaky -- the new colorpicker
            // doesn't fire until you click a button, but the buttons
            // have been hidden.  We work around this by just manually
            // fixing it up here.
            colorpicker.parent().find('.sp-container').removeClass('sp-buttons-disabled');
            $(e.target).hide();
        });

        $('.streams_popover').on('click', 'a.sp-cancel', function () {
            exports.hide_stream_popover();
        });
    });

};

function topic_popover_sub(e) {
    // TODO: use data-stream-id in stream list
    var stream_id = $(e.currentTarget).attr('data-stream-id');
    if (!stream_id) {
        blueslip.error('cannot find stream id');
        return;
    }

    var sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error('Unknown stream: ' + stream_id);
        return;
    }
    return sub;
}

exports.topic_ops = {
    mute: function (stream, topic) {
        exports.hide_topic_popover();
        muting_ui.mute_topic(stream, topic);
        muting_ui.persist_and_rerender();
        muting_ui.notify_with_undo_option(stream, topic);
        muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
    },
    // we don't run a unmute_notify function because it isn't an issue as much
    // if someone accidentally unmutes a stream rather than if they mute it
    // and miss out on info.
    unmute: function (stream, topic) {
        exports.hide_topic_popover();
        muting_ui.unmute_topic(stream, topic);
        muting_ui.persist_and_rerender();
        muting_ui.set_up_muted_topics_ui(muting.get_muted_topics());
    },
};

exports.register_topic_handlers = function () {
    // Narrow to topic
    $('body').on('click', '.narrow_to_topic', function (e) {
        exports.hide_topic_popover();

        var sub = topic_popover_sub(e);
        if (!sub) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');

        var operators = [
            {operator: 'stream', operand: sub.name},
            {operator: 'topic', operand: topic},
        ];
        var opts = {select_first_unread: true, trigger: 'sidebar'};
        narrow.activate(operators, opts);

        e.stopPropagation();
    });

    // Mute the topic
    $('body').on('click', '.sidebar-popover-mute-topic', function (e) {
        var sub = topic_popover_sub(e);
        if (!sub) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.topic_ops.mute(sub.name, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Unmute the topic
    $('body').on('click', '.sidebar-popover-unmute-topic', function (e) {
        var sub = topic_popover_sub(e);
        if (!sub) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.topic_ops.unmute(sub.name, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Mark all messages as read
    $('body').on('click', '.sidebar-popover-mark-topic-read', function (e) {
        var sub = topic_popover_sub(e);
        if (!sub) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.hide_topic_popover();
        unread_ui.mark_topic_as_read(sub.name, topic);
        e.stopPropagation();
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = stream_popover;
}
