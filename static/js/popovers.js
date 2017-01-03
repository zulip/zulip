var popovers = (function () {

var exports = {};

var current_actions_popover_elem;
var current_message_info_popover_elem;
var current_message_reactions_popover_elem;
var emoji_map_is_open = false;

var userlist_placement = "right";

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
        var args = {
            message:  message,
            pm_with_uri: narrow.pm_with_uri(message.sender_email),
            sent_by_uri: narrow.by_sender_uri(message.sender_email),
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

exports.toggle_reactions_popover = function (element, id) {
    var last_popover_elem = current_message_reactions_popover_elem;
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
        var emojis = _.clone(emoji.emojis_name_to_css_class);
        var emojis_used = reactions.get_emojis_used_by_user_for_message_id(id);
        var realm_emojis = emoji.realm_emojis;
        _.each(realm_emojis, function (realm_emoji, realm_emoji_name) {
            emojis[realm_emoji_name] = {
                name: realm_emoji_name,
                is_realm_emoji: true,
                url: realm_emoji.emoji_url
            };
        });
        _.each(emojis_used, function (emoji_name) {
            var is_realm_emoji = emojis[emoji_name].is_realm_emoji;
            var url = emojis[emoji_name].url;
            emojis[emoji_name] = {
                name: emoji_name,
                has_reacted: true,
                css_class: emoji.emoji_name_to_css_class(emoji_name),
                is_realm_emoji: is_realm_emoji,
                url: url
            };
        });

        var args = {
            message_id: id,
            emojis: emojis,
        };

        var approx_popover_height = 400;
        var approx_popover_width = 400;
        var distance_from_bottom = viewport.height() - elt.offset().top;
        var distance_from_right = viewport.width() - elt.offset().left;
        var will_extend_beyond_bottom_of_viewport = distance_from_bottom < approx_popover_height;
        var will_extend_beyond_top_of_viewport = elt.offset().top < approx_popover_height;
        var will_extend_beyond_left_of_viewport = elt.offset().left < (approx_popover_width / 2);
        var will_extend_beyond_right_of_viewport = distance_from_right < (approx_popover_width / 2);
        var placement = 'bottom';
        if (will_extend_beyond_bottom_of_viewport && !will_extend_beyond_top_of_viewport) {
            placement = 'top';
        }
        if (will_extend_beyond_right_of_viewport && !will_extend_beyond_left_of_viewport) {
            placement = 'left';
        }
        if (will_extend_beyond_left_of_viewport && !will_extend_beyond_right_of_viewport) {
            placement = 'right';
        }
        elt.prop('title', '');
        elt.popover({
            placement: placement,
            title:     "",
            content:   templates.render('reaction_popover_content', args),
            trigger:   "manual"
        });
        elt.popover("show");
        elt.prop('title', 'Add reaction...');
        $('.reaction-popover-filter').focus();
        current_message_reactions_popover_elem = elt;
    }
};

exports.toggle_actions_popover = function (element, id) {
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
        var editability = message_edit.get_editability(message);
        var use_edit_icon;
        var editability_menu_item;
        if (editability === message_edit.editability_types.FULL) {
            use_edit_icon = true;
            editability_menu_item = i18n.t("Edit");
        } else if (editability === message_edit.editability_types.TOPIC_ONLY) {
            use_edit_icon = false;
            editability_menu_item = i18n.t("View Source / Edit Topic");
        } else {
            use_edit_icon = false;
            editability_menu_item = i18n.t("View Source");
        }
        var can_mute_topic =
                message.stream &&
                message.subject &&
                !muting.is_topic_muted(message.stream, message.subject);
        var can_unmute_topic =
                message.stream &&
                message.subject &&
                muting.is_topic_muted(message.stream, message.subject);

        var args = {
            message: message,
            use_edit_icon: use_edit_icon,
            editability_menu_item: editability_menu_item,
            can_mute_topic: can_mute_topic,
            can_unmute_topic: can_unmute_topic,
            should_display_add_reaction_option: message.sent_by_me,
            conversation_time_uri: narrow.by_conversation_and_time_uri(message),
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

function get_action_menu_menu_items() {
    return $('li:not(.divider):visible a', current_actions_popover_elem.data('popover').$tip);
}

function focus_first_action_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    var items = get_action_menu_menu_items();
    items.eq(0).expectOne().focus();
}

exports.open_message_menu = function () {
    var id = current_msg_list.selected_id();
    popovers.toggle_actions_popover($(".selected_message .actions_hover")[0], id);
    if (current_actions_popover_elem) {
        focus_first_action_popover_item();
    }
    return true;
};

exports.actions_menu_handle_keyboard = function (key) {
    var items = get_action_menu_menu_items();
    var index = items.index(items.filter(':focus'));

    if (key === "enter" && index >= 0 && index < items.length) {
        return items.eq(index).trigger('click');
    }
    if (index === -1) {
        index = 0;
    } else if ((key === 'down_arrow' || key === 'vim_down') && index < items.length - 1) {
        index += 1;
    } else if ((key === 'up_arrow' || key === 'vim_up') && index > 0) {
        index -= 1;
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

exports.topic_ops = {
    mute: function (stream, topic) {
        popovers.hide_topic_sidebar_popover();
        muting.mute_topic(stream, topic);
        muting_ui.persist_and_rerender();
        muting_ui.notify_with_undo_option(stream, topic);
    },
    // we don't run a unmute_notif function because it isn't an issue as much
    // if someone accidentally unmutes a stream rather than if they mute it
    // and miss out on info.
    unmute: function (stream, topic) {
        popovers.hide_topic_sidebar_popover();
        muting.unmute_topic(stream, topic);
        muting_ui.persist_and_rerender();
    }
};

function message_info_popped() {
    return current_message_info_popover_elem !== undefined;
}

function reaction_popped() {
    return current_message_reactions_popover_elem !== undefined;
}

exports.hide_message_info_popover = function () {
    if (message_info_popped()) {
        current_message_info_popover_elem.popover("destroy");
        current_message_info_popover_elem = undefined;
    }
};

exports.hide_reactions_popover = function () {
    if (reaction_popped()) {
        current_message_reactions_popover_elem.popover("destroy");
        current_message_reactions_popover_elem = undefined;
    }
};

exports.hide_userlist_sidebar = function () {
    $(".app-main .column-right").removeClass("expanded");
};

exports.hide_streamlist_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};

exports.hide_pm_list_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};

exports.show_userlist_sidebar = function () {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
};

exports.show_streamlist_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

exports.show_pm_list_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

var current_stream_sidebar_elem;
var current_topic_sidebar_elem;
var current_user_sidebar_user_id;
var current_user_sidebar_popover;


function user_sidebar_popped() {
    return current_user_sidebar_popover !== undefined;
}

function stream_sidebar_popped() {
    return current_stream_sidebar_elem !== undefined;
}

function topic_sidebar_popped() {
    return current_topic_sidebar_elem !== undefined;
}

exports.hide_emoji_map_popover = function () {
    if (emoji_map_is_open) {
        $('.emoji_popover').css('display', 'none');
        $('.drag').css('display', 'none');
        emoji_map_is_open = false;
    }
};

exports.hide_stream_sidebar_popover = function () {
    if (stream_sidebar_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        current_stream_sidebar_elem = undefined;
    }
};

exports.hide_topic_sidebar_popover = function () {
    if (topic_sidebar_popped()) {
        $(current_topic_sidebar_elem).popover("destroy");
        current_topic_sidebar_elem = undefined;
    }
};

exports.hide_user_sidebar_popover = function () {
    if (user_sidebar_popped()) {
        // this hide_* method looks different from all the others since
        // the presence list may be redrawn. Due to funkiness with jquery's .data()
        // this would confuse $.popover("destroy"), which looks at the .data() attached
        // to a certain element. We thus save off the .data("popover") in the
        // show_user_sidebar_popover and inject it here before calling destroy.
        $('#user_presences').data("popover", current_user_sidebar_popover);
        $('#user_presences').popover("destroy");
        current_user_sidebar_user_id = undefined;
        current_user_sidebar_popover = undefined;
    }
};

function render_emoji_popover() {
    var content = templates.render('emoji_popover_content', {
        emoji_list: emoji.emojis_name_to_css_class
    });

    $('.emoji_popover').append(content);

    $('.drag').show();
    $('.emoji_popover').css('display', 'inline-block');

    $("#new_message_content").focus();

    emoji_map_is_open = true;
}

exports.register_click_handlers = function () {
    $("#main_div").on("click", ".actions_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        popovers.toggle_actions_popover(this, rows.id(row));
    });

    $("#main_div").on("click", ".reaction_button", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        popovers.toggle_reactions_popover(this, rows.id(row));
    });


    $("body").on("click", ".actions_popover .reaction_button", function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        e.preventDefault();
        e.stopPropagation();
        // HACK: Because we need the popover to be based off an
        // element that definitely exists in the page even if the
        // message wasn't sent by us and thus the .reaction_hover
        // element is not present, we use the message's .message_star
        // element as the base for the popover.
        popovers.toggle_reactions_popover($(".selected_message .message_star")[0], msgid);
    });

    $("#main_div").on("click", ".sender_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        show_message_info_popover(this, rows.id(row));
    });

    (function () {
        // create locally scoped variables for drag tracking.
        var meta = {
          drag: false,
          c: {
            y: null
          },
          $popover: $(".emoji_popover"),
          MIN_HEIGHT: 25,
          MAX_HEIGHT: 300
        };

        // drag must start within the .drag zone.
        $(".drag").on("mousedown", function (e) {
            meta.drag = true;
            meta.c.y = e.screenY;
        });

        // mouse move that originated in .drag zone can go anywhere.
        $("body").on("mousemove", function (e) {
            if (meta.drag) {
                var diff = e.screenY - meta.c.y;
                var resolved_height = meta.$popover.height() - diff;

                if (resolved_height > meta.MIN_HEIGHT && resolved_height < meta.MAX_HEIGHT) {
                  meta.$popover.height(resolved_height);
                }
                meta.c.y = e.screenY;
            }
        });

        // drag ends on mouseup. This cancels all drag events without interfering
        // with any other events.
        $("body").on("mouseup", function () {
            meta.drag = false;
        });
    }());

    $("body").on("click", ".emoji_popover", function (e) {
        e.stopPropagation();
    });

    $(".emoji_popover").on("click", ".emoji", function (e) {
        var emoji_choice = $(e.target).attr("title");
        var textarea = $("#new_message_content");
        textarea.val(textarea.val() + " " + emoji_choice);
        textarea.focus();
        e.stopPropagation();
    });

    $("#compose").on("click", "#emoji_map", function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (emoji_map_is_open) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_emoji_map_popover();
            return;
        }
        popovers.hide_all();
        render_emoji_popover();
    });

    $('body').on('click', '.user_popover .narrow_to_private_messages', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;

        popovers.hide_user_sidebar_popover();
        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .narrow_to_messages_sent', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;

        popovers.hide_user_sidebar_popover();
        narrow.by('sender', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .compose_private_message', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;
        popovers.hide_user_sidebar_popover();

        compose.start('private', {private_message_recipient: email, trigger: 'sidebar user actions'});
        e.stopPropagation();
    });

    $('body').on('click', '.user_popover .mention_user', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        compose.start('stream', {trigger: 'sidebar user actions'});
        var name = people.get_person_from_user_id(user_id).full_name;
        var textarea = $("#new_message_content");
        textarea.val('@**' + name + '** ');
        popovers.hide_user_sidebar_popover();
        e.stopPropagation();
        e.preventDefault();
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

    $('body').on('click', '.sender_info_popover .mention_user', function (e) {
        compose.respond_to_message({trigger: 'user sidebar popover'});
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var name = people.get_person_from_user_id(user_id).full_name;
        var textarea = $("#new_message_content");
        textarea.val('@**' + name + '** ');
        popovers.hide_message_info_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $('#user_presences').on('click', 'span.arrow', function (e) {
        e.stopPropagation();

        // use email of currently selected user, rather than some elem comparison,
        // as the presence list may be redrawn with new elements.
        var target = $(this).closest('li');
        var user_id = target.find('a').attr('data-user-id');
        var name = target.find('a').attr('data-name');

        if (current_user_sidebar_user_id === user_id) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_all();
            return;
        }
        popovers.hide_all();

        if (userlist_placement === "right") {
            popovers.show_userlist_sidebar();
        }
        var template_vars = {user_id: user_id, name: name};
        var content = templates.render('user_sidebar_actions', template_vars);

        target.popover({
            content:   content,
            placement: userlist_placement === "left" ? "right" : "left",
            trigger:   "manual",
            fixed: true
        });
        target.popover("show");
        current_user_sidebar_user_id = user_id;
        current_user_sidebar_popover = target.data('popover');

    });

    $('#stream_filters').on('click', '.topic-sidebar-arrow', function (e) {
        var elt = e.target;

        if (topic_sidebar_popped()
            && current_topic_sidebar_elem === elt) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_topic_sidebar_popover();
            e.stopPropagation();
            return;
        }

        popovers.hide_all();
        popovers.show_streamlist_sidebar();

        var stream_name = $(elt).closest('.topic-list').expectOne().attr('data-stream');
        var topic_name = $(elt).closest('li').expectOne().attr('data-name');

        var is_muted = muting.is_topic_muted(stream_name, topic_name);
        var can_mute_topic = !is_muted;
        var can_unmute_topic = is_muted;

        var content = templates.render('topic_sidebar_actions', {
            stream_name: stream_name,
            topic_name: topic_name,
            can_mute_topic: can_mute_topic,
            can_unmute_topic: can_unmute_topic
        });

        $(elt).popover({
            content: content,
            trigger: "manual",
            fixed: true
        });

        $(elt).popover("show");

        current_topic_sidebar_elem = elt;
        e.stopPropagation();
    });

    $('body').on('click', '.narrow_to_topic', function (e) {
        popovers.hide_topic_sidebar_popover();

        var row = $(e.currentTarget).closest('.narrow_to_topic').expectOne();
        var stream_name = row.attr('data-stream-name');
        var topic_name = row.attr('data-topic-name');

        var operators = [
            {operator: 'stream', operand: stream_name},
            {operator: 'topic', operand: topic_name}
        ];
        var opts = {select_first_unread: true, trigger: 'sidebar'};
        narrow.activate(operators, opts);

        e.stopPropagation();
    });

    $('body').on('click', '.sidebar-popover-mute-topic', function (e) {
        var stream = $(e.currentTarget).attr('data-stream-name');
        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.topic_ops.mute(stream, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.sidebar-popover-unmute-topic', function (e) {
        var stream = $(e.currentTarget).attr('data-stream-name');
        var topic = $(e.currentTarget).attr('data-topic-name');
        exports.topic_ops.unmute(stream, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.sidebar-popover-mark-topic-read', function (e) {
        var topic = $(e.currentTarget).attr('data-topic-name');
        var stream = $(e.currentTarget).attr('data-stream-name');
        popovers.hide_topic_sidebar_popover();
        unread.mark_topic_as_read(stream,topic);
        e.stopPropagation();
    });

    $('#stream_filters').on('click', '.stream-sidebar-arrow', function (e) {
        var elt = e.target;
        if (stream_sidebar_popped()
            && current_stream_sidebar_elem === elt) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_stream_sidebar_popover();
            e.stopPropagation();
            return;
        }

        popovers.hide_all();
        popovers.show_streamlist_sidebar();

        var stream = $(elt).parents('li').attr('data-name');

        $(elt).popover({
            content:   templates.render('stream_sidebar_actions', {stream: stream_data.get_sub(stream)}),
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
        var data_id = stream_data.get_sub(stream).stream_id;
        var popover = $('.streams_popover[data-id=' + data_id + ']');
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

            $('.streams_popover').on('click', 'a.sp-cancel', function () {
                popovers.hide_stream_sidebar_popover();
            });
        });

        current_stream_sidebar_elem = elt;
        e.stopPropagation();
    });

    $('body').on('click', '.respond_button', function (e) {
        compose.respond_to_message({trigger: 'popover respond'});
        popovers.hide_actions_popover();
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.respond_personal_button', function (e) {
        compose.respond_to_message({reply_type: 'personal', trigger: 'popover respond pm'});
        popovers.hide_all();
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_narrow_by_id', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        popovers.hide_actions_popover();
        narrow.by_id(msgid, {trigger: 'popover'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_narrow_by_conversation_and_time', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        popovers.hide_actions_popover();
        narrow.by_conversation_and_time(msgid, {trigger: 'popover'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_toggle_collapse', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        var row = current_msg_list.get_row(msgid);
        var message = current_msg_list.get(rows.id(row));

        popovers.hide_actions_popover();

        if (row) {
            if (message.collapsed) {
                condense.uncollapse(row);
            } else {
                condense.collapse(row);
            }
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

    $('body').on('click', '.popover_mute_topic', function (e) {
        var stream = $(e.currentTarget).data('msg-stream');
        var topic = $(e.currentTarget).data('msg-topic');
        popovers.hide_actions_popover();
        exports.topic_ops.mute(stream, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.popover_unmute_topic', function (e) {
        var stream = $(e.currentTarget).data('msg-stream');
        var topic = $(e.currentTarget).data('msg-topic');
        popovers.hide_actions_popover();
        muting.unmute_topic(stream, topic);
        muting_ui.persist_and_rerender();
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
        compose.start('stream', {stream: stream, trigger: 'sidebar stream actions'});
        e.stopPropagation();
    });

    $('body').on('click', '.mark_stream_as_read', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        unread.mark_stream_as_read(stream);
        e.stopPropagation();
    });

    $('body').on('click', '.pin_to_top', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();
        subs.toggle_pin_to_top_stream(stream);
        e.stopPropagation();
    });

    $('body').on('click', '.open_stream_settings', function (e) {
        var stream = $(e.currentTarget).parents('ul').attr('data-name');
        popovers.hide_stream_sidebar_popover();

        window.location.hash = "#subscriptions";
        // the template for subs needs to render.

        subs.onlaunch("narrow_to_row", function () {
            $(".stream-row[data-stream-name='" + stream + "']").click();
        }, true);
    });

    $('.app').on('scroll', function () {
        popovers.hide_all();
    });

};

exports.any_active = function () {
    // True if any popover (that this module manages) is currently shown.
    return popovers.actions_popped() || user_sidebar_popped() || stream_sidebar_popped() ||
        topic_sidebar_popped() || message_info_popped() || emoji_map_is_open ||
        reaction_popped();
};

exports.hide_all = function () {
    popovers.hide_actions_popover();
    popovers.hide_message_info_popover();
    popovers.hide_reactions_popover();
    popovers.hide_stream_sidebar_popover();
    popovers.hide_topic_sidebar_popover();
    popovers.hide_user_sidebar_popover();
    popovers.hide_userlist_sidebar();
    popovers.hide_streamlist_sidebar();
    popovers.hide_emoji_map_popover();
};

exports.set_userlist_placement = function (placement) {
    userlist_placement = placement || "right";
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = popovers;
}
