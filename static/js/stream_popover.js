var render_all_messages_sidebar_actions = require('../templates/all_messages_sidebar_actions.hbs');
var render_delete_topic_modal = require('../templates/delete_topic_modal.hbs');
var render_starred_messages_sidebar_actions = require('../templates/starred_messages_sidebar_actions.hbs');
var render_stream_sidebar_actions = require('../templates/stream_sidebar_actions.hbs');
var render_topic_sidebar_actions = require('../templates/topic_sidebar_actions.hbs');
var render_unstar_messages_modal = require("../templates/unstar_messages_modal.hbs");

// We handle stream popovers and topic popovers in this
// module.  Both are popped up from the left sidebar.
var current_stream_sidebar_elem;
var current_topic_sidebar_elem;
var all_messages_sidebar_elem;
var starred_messages_sidebar_elem;

exports.stream_popped = function () {
    return current_stream_sidebar_elem !== undefined;
};

exports.topic_popped = function () {
    return current_topic_sidebar_elem !== undefined;
};

exports.all_messages_popped = function () {
    return all_messages_sidebar_elem !== undefined;
};

exports.starred_messages_popped = function () {
    return starred_messages_sidebar_elem !== undefined;
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

exports.hide_all_messages_popover = function () {
    if (exports.all_messages_popped()) {
        $(all_messages_sidebar_elem).popover("destroy");
        all_messages_sidebar_elem = undefined;
    }
};

exports.hide_starred_messages_popover = function () {
    if (exports.starred_messages_popped()) {
        $(starred_messages_sidebar_elem).popover("destroy");
        starred_messages_sidebar_elem = undefined;
    }
};

// These are the only two functions that is really shared by the
// two popovers, so we could split out topic stuff to
// another module pretty easily.
exports.show_streamlist_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

exports.hide_streamlist_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};


function stream_popover_sub(e) {
    var stream_id = $(e.currentTarget).parents('ul').attr('data-stream-id');
    var sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error('Unknown stream: ' + stream_id);
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
    var height_delta = after_height - initial_height;
    var top = current_top_px - height_delta / 2;

    if (top < 0) {
        top = 0;
        popover_root.find("div.arrow").hide();
    } else if (top + after_height > $(window).height() - 20) {
        top = $(window).height() - after_height - 20;
        if (top < 0) {
            top = 0;
        }
        popover_root.find("div.arrow").hide();
    }

    popover_root.css('top', top + "px");
}

function build_stream_popover(opts) {
    var elt = opts.elt;
    var stream_id = opts.stream_id;

    if (exports.stream_popped()
        && current_stream_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_stream_popover();
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    var content = render_stream_sidebar_actions({
        stream: stream_data.get_sub_by_id(stream_id),
    });

    $(elt).popover({
        content: content,
        html: true,
        trigger: "manual",
        fixed: true,
        fix_positions: true,
    });

    $(elt).popover("show");
    var popover = $('.streams_popover[data-stream-id=' + stream_id + ']');

    update_spectrum(popover, function (colorpicker) {
        colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options);
    });

    current_stream_sidebar_elem = elt;
}

function build_topic_popover(opts) {
    var elt = opts.elt;
    var stream_id = opts.stream_id;
    var topic_name = opts.topic_name;

    if (exports.topic_popped()
        && current_topic_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_topic_popover();
        return;
    }

    var sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error('cannot build topic popover for stream: ' + stream_id);
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    var is_muted = muting.is_topic_muted(sub.stream_id, topic_name);
    var can_mute_topic = !is_muted;
    var can_unmute_topic = is_muted;

    var content = render_topic_sidebar_actions({
        stream_name: sub.name,
        stream_id: sub.stream_id,
        topic_name: topic_name,
        can_mute_topic: can_mute_topic,
        can_unmute_topic: can_unmute_topic,
        is_admin: sub.is_admin,
    });

    $(elt).popover({
        content: content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");

    current_topic_sidebar_elem = elt;
}

function build_all_messages_popover(e) {
    var elt = e.target;

    if (exports.all_messages_popped()
        && all_messages_sidebar_elem === elt) {
        exports.hide_all_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();

    var content = render_all_messages_sidebar_actions();

    $(elt).popover({
        content: content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");
    all_messages_sidebar_elem = elt;
    e.stopPropagation();

}

function build_starred_messages_popover(e) {
    var elt = e.target;

    if (exports.starred_messages_popped()
        && starred_messages_sidebar_elem === elt) {
        exports.hide_starred_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();

    var content = render_starred_messages_sidebar_actions({
        starred_message_counts: page_params.starred_message_counts,
    });

    $(elt).popover({
        content: content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");
    starred_messages_sidebar_elem = elt;
    e.stopPropagation();

}

exports.register_click_handlers = function () {
    $('#stream_filters').on('click', '.stream-sidebar-arrow', function (e) {
        e.stopPropagation();

        var elt = e.target;
        var stream_id = $(elt).parents('li').attr('data-stream-id');

        build_stream_popover({
            elt: elt,
            stream_id: stream_id,
        });
    });

    $('#stream_filters').on('click', '.topic-sidebar-arrow', function (e) {
        e.stopPropagation();

        var elt = $(e.target).closest('.topic-sidebar-arrow').expectOne()[0];
        var stream_id = $(elt).closest('.narrow-filter').expectOne().attr('data-stream-id');
        var topic_name = $(elt).closest('li').expectOne().attr('data-topic-name');

        build_topic_popover({
            elt: elt,
            stream_id: stream_id,
            topic_name: topic_name,
        });
    });

    $('#global_filters').on('click', '.all-messages-arrow', build_all_messages_popover);

    $('#global_filters').on('click', '.starred-messages-sidebar-arrow', build_starred_messages_popover);

    exports.register_stream_handlers();
    exports.register_topic_handlers();
};

exports.register_stream_handlers = function () {
    // Stream settings
    $('body').on('click', '.open_stream_settings', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();

        var stream_edit_hash = hash_util.stream_edit_uri(sub);
        hashchange.go_to_location(stream_edit_hash);
    });

    // Pin/unpin
    $('body').on('click', '.pin_to_top', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        subs.toggle_pin_to_top_stream(sub);
        e.stopPropagation();
    });

    // Mark all messages in stream as read
    $('body').on('click', '.mark_stream_as_read', function (e) {
        var sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        unread_ops.mark_stream_as_read(sub.stream_id);
        e.stopPropagation();
    });

    // Mark all messages as read
    $('body').on('click', '#mark_all_messages_as_read', function (e) {
        exports.hide_all_messages_popover();
        pointer.fast_forward_pointer();
        e.stopPropagation();
    });

    // Unstar all messages
    $('body').on('click', '#unstar_all_messages', function (e) {
        exports.hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        $(".left-sidebar-modal-holder").empty();
        $(".left-sidebar-modal-holder").html(render_unstar_messages_modal());
        $("#unstar-messages-modal").modal("show");
    });

    $('body').on('click', '#do_unstar_messages_button', function (e) {
        $("#unstar-messages-modal").modal("hide");
        message_flags.unstar_all_messages();
        e.stopPropagation();
    });

    // Toggle displaying starred message count
    $('body').on('click', '#toggle_display_starred_msg_count', function (e) {
        exports.hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        var starred_msg_counts = page_params.starred_message_counts;
        var data = {};
        data.starred_message_counts = JSON.stringify(!starred_msg_counts);
        channel.patch({
            url: '/json/settings/display',
            data: data,
        });
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

function topic_popover_stream_id(e) {
    // TODO: use data-stream-id in stream list
    var stream_id = $(e.currentTarget).attr('data-stream-id');

    return stream_id;
}

function topic_popover_sub(e) {
    // TODO: use data-stream-id in stream list
    var stream_id = topic_popover_stream_id(e);
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
        narrow.activate(operators, {trigger: 'sidebar'});

        e.stopPropagation();
    });

    // Mute the topic
    $('body').on('click', '.sidebar-popover-mute-topic', function (e) {
        var stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        muting_ui.mute(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Unmute the topic
    $('body').on('click', '.sidebar-popover-unmute-topic', function (e) {
        var stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        muting_ui.unmute(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Mark all messages as read
    $('body').on('click', '.sidebar-popover-mark-topic-read', function (e) {
        var stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.hide_topic_popover();
        unread_ops.mark_topic_as_read(stream_id, topic);
        e.stopPropagation();
    });

    // Deleting all message in a topic
    $('body').on('click', '.sidebar-popover-delete-topic-messages', function (e) {
        var stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        var topic = $(e.currentTarget).attr('data-topic-name');
        var args = {
            topic_name: topic,
        };

        exports.hide_topic_popover();

        $('#delete-topic-modal-holder').html(render_delete_topic_modal(args));

        $('#do_delete_topic_button').on('click', function () {
            message_edit.delete_topic(stream_id, topic);
        });

        $('#delete_topic_modal').modal('show');

        e.stopPropagation();
    });
};

window.stream_popover = exports;
