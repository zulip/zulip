var popovers = (function () {

var exports = {};

var current_actions_popover_elem;
var current_message_info_popover_elem;

function show_message_info_popover(element, id) {
    var last_popover_elem = current_message_info_popover_elem;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    current_msg_list.select_id(id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        timerender.set_full_datetime(current_msg_list.get(id),
                                     elt.closest(".message_row").find(".message_time"));

        var message = current_msg_list.get(id);
        var can_edit = message.sent_by_me;
        var args = {
            message:  message,
            can_edit_message: can_edit,
            narrowed: narrow.active()
        };

        var ypos = elt.offset().top - viewport.scrollTop();
        elt.popover({
            placement: (ypos > (viewport.height() - 300)) ? 'top' : 'bottom',
            title:     templates.render('message_info_popover_title',   args),
            content:   templates.render('message_info_popover_content', args),
            trigger:   "manual"
        });
        elt.popover("show");
        current_message_info_popover_elem = elt;
    }
}

exports.show_actions_popover = function (element, id) {
    var last_popover_elem = current_actions_popover_elem;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    current_msg_list.select_id(id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        var message = current_msg_list.get(id);
        var can_edit = message.sent_by_me;
        var args = {
            message:  message,
            can_edit_message: can_edit,
            narrowed: narrow.active()
        };

        var ypos = elt.offset().top - viewport.scrollTop();
        elt.popover({
            placement: (ypos > (viewport.height() - 300)) ? 'top' : 'bottom',
            title:     "",
            content:   templates.render('actions_popover_content', args),
            trigger:   "manual"
        });
        elt.popover("show");
        current_actions_popover_elem = elt;
    }
};

exports.actions_menu_handle_keyboard = function (key) {
    var items = $('li:not(.divider):visible a', current_actions_popover_elem.data('popover').$tip);
    var index = items.index(items.filter(':focus'));

    if (key === "enter" && index >= 0 && index < items.length) {
        return items.eq(index).trigger('click');
    }
    if (index === -1) {
        index = 0;
    }
    else if ((key === 'down_arrow' || key === 'vim_down') && index < items.length - 1) {
        ++index;
    }
    else if ((key === 'up_arrow' || key === 'vim_up') && index > 0) {
        --index;
    }
    items.eq(index).focus();
};

exports.actions_popped = function () {
    return current_actions_popover_elem !== undefined;
};

exports.hide_actions_popover = function () {
    if (popovers.actions_popped()) {
        current_actions_popover_elem.popover("destroy");
        current_actions_popover_elem = undefined;
    }
};

function message_info_popped() {
    return current_message_info_popover_elem !== undefined;
}

exports.hide_message_info_popover = function () {
    if (message_info_popped()) {
        current_message_info_popover_elem.popover("destroy");
        current_message_info_popover_elem = undefined;
    }
};



var current_stream_sidebar_elem;
var current_user_sidebar_elem;

function user_sidebar_popped() {
    return current_user_sidebar_elem !== undefined;
}

function stream_sidebar_popped() {
    return current_stream_sidebar_elem !== undefined;
}

exports.hide_stream_sidebar_popover = function () {
    if (stream_sidebar_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        current_stream_sidebar_elem = undefined;
    }
};

exports.hide_user_sidebar_popover = function () {
    if (user_sidebar_popped()) {
        current_user_sidebar_elem.popover("destroy");
        current_user_sidebar_elem = undefined;
    }
};

exports.show_user_sidebar_popover = function () {
    // TODO: implement & use
};

exports.register_click_handlers = function () {
    $("#main_div").on("click", ".actions_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        popovers.show_actions_popover(this, rows.id(row));
    });

    $("#main_div").on("click", ".sender_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        show_message_info_popover(this, rows.id(row));
    });


    $('#user_presences').on('click', 'span.arrow', function (e) {
        var last_sidebar_elem = current_user_sidebar_elem;
        popovers.hide_all();

        var target = $(e.target).closest('li');
        var email = target.find('a').attr('data-email');
        var name = target.find('a').attr('data-name');

        target.popover({
            content:   templates.render('user_sidebar_actions', {'email': email,
                                                                 'name': name}),
            placement: "left",
            trigger:   "manual",
            fixed: true
        });
        target.popover("show");
        current_user_sidebar_elem = target;
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .narrow_to_private_messages', function (e) {
        var email = $(e.target).parents('ul').attr('data-email');
        popovers.hide_user_sidebar_popover();
        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .narrow_to_messages_sent', function (e) {
        var email = $(e.target).parents('ul').attr('data-email');
        popovers.hide_user_sidebar_popover();
        narrow.by('sender', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .compose_private_message', function (e) {
        var email = $(e.target).parents('ul').attr('data-email');
        popovers.hide_user_sidebar_popover();
        compose.start('private', {"private_message_recipient": email, trigger: 'sidebar user actions'});
        e.stopPropagation();
    });

    $('body').on('click', '.sender_info_popover .narrow_to_private_messages', function (e) {
        var email = $(e.target).parents('ul').attr('data-email');
        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        popovers.hide_message_info_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.sender_info_popover .narrow_to_messages_sent', function (e) {
        var email = $(e.target).parents('ul').attr('data-email');
        narrow.by('sender', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        popovers.hide_message_info_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $('#stream_filters').on('click', 'span.arrow', function (e) {
        var elt = e.target;
        if (stream_sidebar_popped()
            && current_stream_sidebar_elem === elt) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_stream_sidebar_popover();
            return;
        }

        var last_sidebar_elem = current_stream_sidebar_elem;
        popovers.hide_all();

        var stream = $(elt).parents('li').attr('data-name');

        var ypos = $(elt).offset().top - viewport.scrollTop();
        $(elt).popover({
            content:   templates.render('stream_sidebar_actions', {'stream': subs.get(stream)}),
            trigger:   "manual",
            fixed: true
        });

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

        $(elt).popover("show");
        var popover = $('.streams_popover[data-id=' + subs.get(stream).id + ']');
        update_spectrum(popover, function (colorpicker) {
            colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options);
        });

        $('.streams_popover').on('click', '.custom_color', function (e) {
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

            $('.streams_popover').on('click', 'a.sp-cancel', function (e) {
                popovers.hide_stream_sidebar_popover();
            });
        });

        current_stream_sidebar_elem = elt;
        e.stopPropagation();
    });

    $('body').on('click', '.respond_button', function (e) {
        respond_to_message({trigger: 'popover respond'});
        popovers.hide_actions_popover();
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.respond_personal_button', function (e) {
        respond_to_message({reply_type: 'personal', trigger: 'popover respond pm'});
        popovers.hide_all();
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_narrow_by_subject_button', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        popovers.hide_actions_popover();
        narrow.by_subject(msgid, {trigger: 'popover'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_narrow_by_recipient_button', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        popovers.hide_actions_popover();
        narrow.by_recipient(msgid, {trigger: 'popover'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_narrow_by_time_travel_button', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        popovers.hide_actions_popover();
        narrow.by_time_travel(msgid, {trigger: 'popover'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_toggle_collapse', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        var row = current_msg_list.get_row(msgid);
        var message = current_msg_list.get(rows.id(row));

        popovers.hide_actions_popover();

        if (message.collapsed) {
            ui.uncollapse(row);
        } else {
            ui.collapse(row);
        }

        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_edit_message', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        var row = current_msg_list.get_row(msgid);
        popovers.hide_actions_popover();
        message_edit.start(row);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.toggle_home', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        subs.toggle_home(stream);
        e.stopPropagation();
    });

    $('body').on('click', '.narrow_to_stream', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        narrow.by('stream', stream, {select_first_unread: true, trigger: 'sidebar popover'});
        e.stopPropagation();
    });

    $('body').on('click', '.compose_to_stream', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        compose.start('stream', {"stream": stream, trigger: 'sidebar stream actions'});
        e.stopPropagation();
    });

    $('body').on('click', '.open_stream_settings', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        if (! $('#subscriptions').hasClass('active')) {
            // Go to streams page and once it loads, expand the relevant
            // stream's settings.
            $(document).one('subs_page_loaded.zulip', function (event) {
                subs.show_settings_for(stream);
            });
            ui.change_tab_to('#subscriptions');
        } else {
            // Already on streams page, so just expand the relevant stream.
            subs.show_settings_for(stream);
        }
    });

};

exports.any_active = function () {
    // True if any popover (that this module manages) is currently shown.
    return popovers.actions_popped() || user_sidebar_popped() || stream_sidebar_popped() || message_info_popped();
};

exports.hide_all = function () {
    popovers.hide_actions_popover();
    popovers.hide_message_info_popover();
    popovers.hide_stream_sidebar_popover();
    popovers.hide_user_sidebar_popover();
};

return exports;
}());
