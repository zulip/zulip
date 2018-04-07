var popovers = (function () {

var exports = {};

var current_actions_popover_elem;
var current_flatpickr_instance;
var current_message_info_popover_elem;
var userlist_placement = "right";

var list_of_popovers = [];

// this utilizes the proxy pattern to intercept all calls to $.fn.popover
// and push the $.fn.data($o, "popover") results to an array.
// this is needed so that when we try to unload popovers, we can kill all dead
// ones that no longer have valid parents in the DOM.
(function (popover) {

    $.fn.popover = function () {
        // apply the jQuery object as `this`, and popover function arguments.
        popover.apply(this, arguments);

        // if there is a valid "popover" key in the jQuery data object then
        // push it to the array.
        if (this.data("popover")) {
            list_of_popovers.push(this.data("popover"));
        }
    };

    // add back all shallow properties of $.fn.popover to the new proxied version.
    for (var x in popover) {
        if (popover.hasOwnProperty(x)) {
            $.fn.popover[x] = popover[x];
        }
    }
}($.fn.popover));

function copy_email_handler(e) {
    var email_el = $(e.trigger.parentElement);
    var copy_icon = email_el.find('i');

    // only change the parent element's text back to email
    // and not overwrite the tooltip.
    var email_textnode = email_el[0].childNodes[2];

    email_el.addClass('email_copied');
    email_textnode.nodeValue = i18n.t('Email copied');

    setTimeout(function () {
      email_el.removeClass('email_copied');
      email_textnode.nodeValue = copy_icon.attr('data-clipboard-text');
    }, 1500);
    e.clearSelection();
}

function init_email_clipboard() {
    $('.user_popover_email').each(function () {
        if (this.clientWidth < this.scrollWidth) {
            var email_el = $(this);
            var copy_email_icon = email_el.find('i');
            copy_email_icon.removeClass('hide_copy_icon');

            var copy_email_clipboard = new ClipboardJS(copy_email_icon[0]);
            copy_email_clipboard.on('success', copy_email_handler);
        }
    });
}

function load_medium_avatar(user, elt) {
    var user_avatar_url = "avatar/" + user.user_id + "/medium";
    var sender_avatar_medium = new Image();
    sender_avatar_medium.src = user_avatar_url;
    $(sender_avatar_medium).on("load", function () {
        elt.css("background-image", "url(" + $(this).attr("src") + ")");
    });
}

function user_last_seen_time_status(user_id) {
    var status = presence.get_status(user_id);
    if (status === "active") {
        return i18n.t("Active now");
    }

    if (page_params.realm_is_zephyr_mirror_realm) {
        // We don't send presence data to clients in Zephyr mirroring realms
        return i18n.t("Unknown");
    }

    // There are situations where the client has incomplete presence
    // history on a user.  This can happen when users are deactivated,
    // or when they just haven't been present in a long time (and we
    // may have queries on presence that go back only N weeks).
    //
    // We give the somewhat vague status of "Unknown" for these users.
    var last_active_date = presence.last_active_date(user_id);
    if (last_active_date === undefined) {
        return i18n.t("Unknown");
    }
    return timerender.last_seen_status_from_date(last_active_date.clone());
}

function calculate_info_popover_placement(size, elt) {
  var ypos = elt.offset().top;

  if (!((ypos + (size / 2) < message_viewport.height()) &&
      (ypos > (size / 2)))) {
      if (((ypos + size) < message_viewport.height())) {
          return 'bottom';
      } else if (ypos > size) {
          return 'top';
      }
  }
}

// exporting for testability
exports._test_calculate_info_popover_placement = calculate_info_popover_placement;

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function show_user_info_popover(element, user, message) {
    var last_popover_elem = current_message_info_popover_elem;
    var popover_size = 428; // hardcoded pixel height of the popover
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    current_msg_list.select_id(message.id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        if (user === undefined) {
            // This is never supposed to happen, not even for deactivated
            // users, so we'll need to debug this error if it occurs.
            blueslip.error('Bad sender in message' + message.sender_id);
            return;
        }

        var args = {
            user_full_name: user.full_name,
            user_email: user.email,
            user_id: user.user_id,
            user_time: people.get_user_time(user.user_id),
            presence_status: presence.get_status(user.user_id),
            user_last_seen_time_status: user_last_seen_time_status(user.user_id),
            pm_with_uri: narrow.pm_with_uri(user.email),
            sent_by_uri: narrow.by_sender_uri(user.email),
            narrowed: narrow_state.active(),
            private_message_class: "respond_personal_button",
            is_me: people.is_current_user(user.email),
            is_active: people.is_active_user_for_popover(user.user_id),
            is_bot: people.get_person_from_user_id(user.user_id).is_bot,
            is_sender_popover: message.sender_id === user.user_id,
        };


        elt.popover({
            placement: calculate_info_popover_placement(popover_size, elt),
            template: templates.render('user_info_popover', {class: "message-info-popover"}),
            title: templates.render('user_info_popover_title',
                                    {user_avatar: "avatar/" + user.email}),
            content: templates.render('user_info_popover_content', args),
            trigger: "manual",
        });
        elt.popover("show");

        init_email_clipboard();
        load_medium_avatar(user, $(".popover-avatar"));

        current_message_info_popover_elem = elt;
    }
}

function fetch_group_members(member_ids) {
    return member_ids
        .map(function (m) {
            return people.get_person_from_user_id(m);
        })
        .filter(function (m) {
            return m !== undefined;
        })
        .map(function (p) {
            return Object.assign({}, p, {
                presence_status: presence.get_status(p.user_id),
                is_active: people.is_active_user_for_popover(p.user_id),
                user_last_seen_time_status: user_last_seen_time_status(p.user_id),
            });
        });
}

function sort_group_members(members) {
    return members
        .sort(function (a, b) {
              return a.full_name.localeCompare(b.full_name);
        });
}

// exporting these functions for testing purposes
exports._test_fetch_group_members = fetch_group_members;
exports._test_sort_group_members = sort_group_members;

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function show_user_group_info_popover(element, group, message) {
    var last_popover_elem = current_message_info_popover_elem;
    // hardcoded pixel height of the popover
    // note that the actual size varies (in group size), but this is about as big as it gets
    var popover_size = 390;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    current_msg_list.select_id(message.id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        var args = {
            group_name: group.name,
            group_description: group.description,
            members: sort_group_members(fetch_group_members(group.members.keys())),
        };
        elt.popover({
            placement: calculate_info_popover_placement(popover_size, elt),
            template: templates.render('user_group_info_popover', {class: "message-info-popover"}),
            content: templates.render('user_group_info_popover_content', args),
            trigger: "manual",
        });
        elt.popover("show");
        ui.set_up_scrollbar($('.group-info-popover .member-list'));
        current_message_info_popover_elem = elt;
    }
}

exports.toggle_actions_popover = function (element, id) {
    var last_popover_elem = current_actions_popover_elem;
    popovers.hide_all();
    if (last_popover_elem !== undefined
        && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    $(element).closest('.message_row').toggleClass('has_popover has_actions_popover');
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
            editability_menu_item = i18n.t("View source / Edit topic");
        } else {
            use_edit_icon = false;
            editability_menu_item = i18n.t("View source");
        }
        var can_mute_topic =
                message.stream &&
                message.subject &&
                !muting.is_topic_muted(message.stream, message.subject);
        var can_unmute_topic =
                message.stream &&
                message.subject &&
                muting.is_topic_muted(message.stream, message.subject);

        var should_display_edit_history_option = _.any(message.edit_history, function (entry) {
            return entry.prev_content !== undefined;
        }) && page_params.realm_allow_edit_history;
        var should_display_delete_option = page_params.is_admin ||
            (message.sent_by_me && page_params.realm_allow_message_deleting);

        var should_display_collapse = !message.locally_echoed && !message.collapsed;
        var should_display_uncollapse = !message.locally_echoed && message.collapsed;

        var should_display_edit_and_view_source =
                message.content !== '<p>(deleted)</p>' ||
                editability === message_edit.editability_types.FULL ||
                editability === message_edit.editability_types.TOPIC_ONLY;
        var should_display_quote_and_reply = message.content !== '<p>(deleted)</p>';

        var args = {
            message: message,
            use_edit_icon: use_edit_icon,
            editability_menu_item: editability_menu_item,
            can_mute_topic: can_mute_topic,
            can_unmute_topic: can_unmute_topic,
            should_display_collapse: should_display_collapse,
            should_display_uncollapse: should_display_uncollapse,
            should_display_add_reaction_option: message.sent_by_me,
            should_display_edit_history_option: should_display_edit_history_option,
            conversation_time_uri: narrow.by_conversation_and_time_uri(message, true),
            narrowed: narrow_state.active(),
            should_display_delete_option: should_display_delete_option,
            should_display_reminder_option: feature_flags.reminders_in_message_action_menu,
            should_display_edit_and_view_source: should_display_edit_and_view_source,
            should_display_quote_and_reply: should_display_quote_and_reply,
        };

        var ypos = elt.offset().top;
        elt.popover({
            // Popover height with 7 items in it is ~190 px
            placement: ((message_viewport.height() - ypos) < 220) ? 'top' : 'bottom',
            title:     "",
            content:   templates.render('actions_popover_content', args),
            trigger:   "manual",
        });
        elt.popover("show");
        current_actions_popover_elem = elt;
    }
};

function do_set_reminder(msgid, timestamp) {
    var message = current_msg_list.get(msgid);
    var link_to_msg = narrow.by_conversation_and_time_uri(message, true);
    var command = compose.deferred_message_types.reminders.slash_command;
    var reminder_timestamp = timestamp;
    var custom_msg = '[this message](' + link_to_msg + ') at ' + reminder_timestamp;
    var reminder_msg_content = command + ' ' + reminder_timestamp + '\n' + custom_msg;
    var reminder_message = {
        type: "private",
        content: reminder_msg_content,
        sender_id: page_params.user_id,
        stream: '',
        subject: '',
    };
    var recipient = page_params.email;
    var emails = util.extract_pm_recipients(recipient);
    reminder_message.to = emails;
    reminder_message.reply_to = recipient;
    reminder_message.private_message_recipient = recipient;
    reminder_message.to_user_ids = people.email_list_to_user_ids_string(emails);

    var row = $("[zid='" + msgid + "']");

    function success() {
        row.find(".alert-msg")
            .text(i18n.t("Reminder set!"))
            .css("display", "block")
            .delay(1000).fadeOut(300);
    }

    function error() {
        row.find(".alert-msg")
            .text(i18n.t("Setting reminder failed!"))
            .css("display", "block")
            .delay(1000).fadeOut(300);
    }

    compose.schedule_message(reminder_message, success, error);
}

exports.render_actions_remind_popover = function (element, id) {
    popovers.hide_all();
    $(element).closest('.message_row').toggleClass('has_popover has_actions_popover');
    current_msg_list.select_id(id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        var message = current_msg_list.get(id);
        var args = {
            message: message,
        };
        var ypos = elt.offset().top;
        elt.popover({
            // Popover height with 7 items in it is ~190 px
            placement: ((message_viewport.height() - ypos) < 220) ? 'top' : 'bottom',
            title:     "",
            content:   templates.render('remind_me_popover_content', args),
            trigger:   "manual",
        });
        elt.popover("show");
        current_flatpickr_instance = $('.remind.custom[data-message-id="'+message.id+'"]').flatpickr({
            enableTime: true,
            clickOpens: false,
            minDate: 'today',
            plugins: [new confirmDatePlugin({})], // eslint-disable-line new-cap, no-undef
        });
        current_actions_popover_elem = elt;
    }
};

function get_action_menu_menu_items() {
    if (!current_actions_popover_elem) {
        blueslip.error('Trying to get menu items when action popover is closed.');
        return;
    }

    var popover_data = current_actions_popover_elem.data('popover');
    if (!popover_data) {
        blueslip.error('Cannot find popover data for actions menu.');
        return;
    }

    return $('li:not(.divider):visible a', popover_data.$tip);
}

function focus_first_action_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    var items = get_action_menu_menu_items();
    if (!items) {
        return;
    }

    items.eq(0).expectOne().focus();
}

exports.open_message_menu = function (message) {
    if (message.locally_echoed) {
        // Don't open the popup for locally echoed messages for now.
        // It creates bugs with things like keyboard handlers when
        // we get the server response.
        return true;
    }

    var id = message.id;
    popovers.toggle_actions_popover($(".selected_message .actions_hover")[0], id);
    if (current_actions_popover_elem) {
        focus_first_action_popover_item();
    }
    return true;
};

exports.actions_menu_handle_keyboard = function (key) {
    var items = get_action_menu_menu_items();
    if (!items) {
        return;
    }

    var index = items.index(items.filter(':focus'));

    if (key === "enter" && index >= 0 && index < items.length) {
        return items[index].click();
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
        $('.has_popover').removeClass('has_popover has_actions_popover');
        current_actions_popover_elem.popover("destroy");
        current_actions_popover_elem = undefined;
    }
    if (current_flatpickr_instance !== undefined) {
        current_flatpickr_instance.destroy();
        current_flatpickr_instance = undefined;
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

exports.hide_userlist_sidebar = function () {
    $(".app-main .column-right").removeClass("expanded");
};

exports.hide_pm_list_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};

exports.show_userlist_sidebar = function () {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
};

exports.show_pm_list_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

var current_user_sidebar_user_id;
var current_user_sidebar_popover;

function user_sidebar_popped() {
    return current_user_sidebar_popover !== undefined;
}

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

exports.show_sender_info = function () {
    var $message = $(".selected_message");
    var $sender = $message.find(".sender_info_hover");
    var $prev_message = $message.prev();
    while (!$sender[0]) {
        $prev_message = $prev_message.prev();
        if (!$prev_message) {
            break;
        }
        $sender = $prev_message.find(".sender_info_hover");
    }
    var message = current_msg_list.get(rows.id($message));
    var user = people.get_person_from_user_id(message.sender_id);
    show_user_info_popover($sender[0], user, message);
};

exports.register_click_handlers = function () {
    $("#main_div").on("click", ".actions_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        popovers.toggle_actions_popover(this, rows.id(row));
    });

    $("#main_div").on("click", ".sender_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        var message = current_msg_list.get(rows.id(row));
        var user = people.get_person_from_user_id(message.sender_id);
        show_user_info_popover(this, user, message);
    });

    $("#main_div").on("click", ".user-mention", function (e) {
        var id = $(this).attr('data-user-id');
        // We fallback to email to handle legacy markdown that was rendered
        // before we cut over to using data-user-id
        var email = $(this).attr('data-user-email');
        if (id === '*' || email === '*') {
            return;
        }
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        var message = current_msg_list.get(rows.id(row));
        var user;
        if (id) {
            user = people.get_person_from_user_id(id);
        } else {
            user = people.get_by_email(email);
        }
        show_user_info_popover(this, user, message);
    });

    $("#main_div").on("click", ".user-group-mention", function (e) {
        var id = $(this).attr('data-user-group-id');
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        var message = current_msg_list.get(rows.id(row));
        var group = user_groups.get_user_group_from_id(id);
        if (group === undefined) {
            blueslip.error('Unable to find user group in message' + message.sender_id);
        } else {
            show_user_group_info_popover(this, group, message);
        }
    });


    $('body').on('click', '.info_popover_actions .narrow_to_private_messages', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;
        popovers.hide_message_info_popover();
        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.info_popover_actions .narrow_to_messages_sent', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;
        popovers.hide_message_info_popover();
        narrow.by('sender', email, {select_first_unread: true, trigger: 'user sidebar popover'});
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.user_popover .mention_user', function (e) {
        if (!compose_state.composing()) {
            compose_actions.start('stream', {trigger: 'sidebar user actions'});
        }
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var name = people.get_person_from_user_id(user_id).full_name;
        compose_ui.insert_syntax_and_focus('@**' + name + '**');
        popovers.hide_user_sidebar_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.message-info-popover .mention_user', function (e) {
        if (!compose_state.composing()) {
            compose_actions.respond_to_message({trigger: 'user sidebar popover'});
        }
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var name = people.get_person_from_user_id(user_id).full_name;
        compose_ui.insert_syntax_and_focus('@**' + name + '**');
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

        if (current_user_sidebar_user_id === user_id) {
            // If the popover is already shown, clicking again should toggle it.
            popovers.hide_all();
            return;
        }
        popovers.hide_all();

        if (userlist_placement === "right") {
            popovers.show_userlist_sidebar();
        }

        var user = people.get_person_from_user_id(user_id);
        var user_email = user.email;

        var args = {
            user_email: user_email,
            user_full_name: user.full_name,
            user_id: user_id,
            user_time: people.get_user_time(user_id),
            presence_status: presence.get_status(user_id),
            user_last_seen_time_status: user_last_seen_time_status(user_id),
            pm_with_uri: narrow.pm_with_uri(user_email),
            sent_by_uri: narrow.by_sender_uri(user_email),
            private_message_class: "compose_private_message",
            is_active: people.is_active_user_for_popover(user_id),
            is_bot: user.is_bot,
            is_sender_popover: false,
        };

        target.popover({
            template: templates.render('user_info_popover', {class: "user_popover"}),
            title: templates.render('user_info_popover_title', {user_avatar: "avatar/" + user_email}),
            content: templates.render('user_info_popover_content', args),
            trigger: "manual",
            fixed: true,
            placement: userlist_placement === "left" ? "right" : "left",
        });
        target.popover("show");

        init_email_clipboard();
        load_medium_avatar(user, $(".popover-avatar"));

        current_user_sidebar_user_id = user_id;
        current_user_sidebar_popover = target.data('popover');
    });

    $('body').on("mouseenter", ".user_popover_email", function () {
        var tooltip_holder = $(this).find('div');

        if (this.offsetWidth < this.scrollWidth) {
            tooltip_holder.addClass('display-tooltip');
        } else {
            tooltip_holder.removeClass('display-tooltip');
        }
    });

    $('body').on('click', '.respond_button', function (e) {
        // Arguably, we should fetch the message ID to respond to from
        // e.target, but that should always be the current selected
        // message in the current message list (and
        // compose_actions.respond_to_message doesn't take a message
        // argument).
        compose_actions.quote_and_reply({trigger: 'popover respond'});
        popovers.hide_actions_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.reminder_button', function (e) {
        var msgid = $(e.currentTarget).data('message-id');
        popovers.render_actions_remind_popover($(".selected_message .actions_hover")[0], msgid);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.remind.custom', function (e) {
        $(e.currentTarget)[0]._flatpickr.toggle();
        e.stopPropagation();
        e.preventDefault();
    });

    function reminder_click_handler(datestr, e) {
        var id = $(".remind.custom").data('message-id');
        do_set_reminder(id, datestr);
        popovers.hide_all();
        e.stopPropagation();
        e.preventDefault();
    }

    $('body').on('click', '.remind.in_20m', function (e) {
        var datestr = moment().add(20, 'm').format();
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.remind.in_1h', function (e) {
        var datestr = moment().add(1, 'h').format();
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.remind.in_3h', function (e) {
        var datestr = moment().add(3, 'h').format();
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.remind.tomo', function (e) {
        var datestr = moment().add(1, 'd').hour(9).minute(0).seconds(0).format();
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.remind.nxtw', function (e) {
        var datestr = moment().add(1, 'w').day('monday').hour(9).minute(0).seconds(0).format();
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.flatpickr-calendar', function (e) {
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.flatpickr-confirm', function (e) {
        var datestr = $(".remind.custom")[0].value;
        reminder_click_handler(datestr, e);
    });

    $('body').on('click', '.respond_personal_button, .compose_private_message', function (e) {
        var user_id = $(e.target).parents('ul').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;
        compose_actions.start('private', {
            trigger: 'popover send private',
            private_message_recipient: email});
        popovers.hide_all();
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.popover_toggle_collapse', function (e) {
        var msgid = $(e.currentTarget).data('message-id');
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
        var msgid = $(e.currentTarget).data('message-id');
        var row = current_msg_list.get_row(msgid);
        popovers.hide_actions_popover();
        message_edit.start(row);
        e.stopPropagation();
        e.preventDefault();
    });
    $('body').on('click', '.view_edit_history', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        var row = current_msg_list.get_row(msgid);
        var message = current_msg_list.get(rows.id(row));
        var message_history_cancel_btn = $('#message-history-cancel');

        popovers.hide_actions_popover();
        message_edit.show_history(message);
        message_history_cancel_btn.focus();
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.popover_mute_topic', function (e) {
        var stream = $(e.currentTarget).data('msg-stream');
        var topic = $(e.currentTarget).data('msg-topic');
        popovers.hide_actions_popover();
        muting_ui.mute(stream, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.popover_unmute_topic', function (e) {
        var stream = $(e.currentTarget).data('msg-stream');
        var topic = $(e.currentTarget).data('msg-topic');
        popovers.hide_actions_popover();
        muting_ui.unmute(stream, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $('body').on('click', '.delete_message', function (e) {
        var msgid = $(e.currentTarget).data('message-id');
        popovers.hide_actions_popover();
        message_edit.delete_message(msgid);
        e.stopPropagation();
        e.preventDefault();
    });

    new ClipboardJS('.copy_link');

    $('body').on('click', '.copy_link', function (e) {
        popovers.hide_actions_popover();
        var id = $(this).attr("data-message-id");
        var row = $("[zid='" + id + "']");
        row.find(".alert-msg")
            .text(i18n.t("Copied!"))
            .css("display", "block")
            .delay(1000).fadeOut(300);

        setTimeout(function () {
            // The Cliboard library works by focusing to a hidden textarea.
            // We unfocus this so keyboard shortcuts, etc., will work again.
            $(":focus").blur();
        }, 0);

        e.stopPropagation();
        e.preventDefault();
    });

    (function () {
        var last_scroll = 0;

        $('.app').on('scroll', function () {
            var date = new Date().getTime();

            // only run `popovers.hide_all()` if the last scroll was more
            // than 250ms ago.
            if (date - last_scroll > 250) {
                popovers.hide_all();
            }

            // update the scroll time on every event to make sure it doesn't
            // retrigger `hide_all` while still scrolling.
            last_scroll = date;
        });
    }());
};

exports.any_active = function () {
    // True if any popover (that this module manages) is currently shown.
    // Expanded sidebars on mobile view count as popovers as well.
    return popovers.actions_popped() || user_sidebar_popped() ||
        stream_popover.stream_popped() || stream_popover.topic_popped() ||
        message_info_popped() || emoji_picker.reactions_popped() ||
        $("[class^='column-'].expanded").length;
};

exports.hide_all = function () {
    $('.has_popover').removeClass('has_popover has_actions_popover has_emoji_popover');
    popovers.hide_actions_popover();
    popovers.hide_message_info_popover();
    emoji_picker.hide_emoji_popover();
    stream_popover.hide_stream_popover();
    stream_popover.hide_topic_popover();
    stream_popover.hide_all_messages_popover();
    popovers.hide_user_sidebar_popover();
    popovers.hide_userlist_sidebar();
    stream_popover.restore_stream_list_size();

    // look through all the popovers that have been added and removed.
    list_of_popovers.forEach(function ($o) {
        if (!document.body.contains($o.$element[0]) && $o.$tip) {
            $o.$tip.remove();
        }
    });
    list_of_popovers = [];
};

exports.set_userlist_placement = function (placement) {
    userlist_placement = placement || "right";
};

exports.compute_placement = function (elt, popover_height, popover_width,
                                      prefer_vertical_positioning) {
    var client_rect = elt.get(0).getBoundingClientRect();
    var distance_from_top = client_rect.top;
    var distance_from_bottom = message_viewport.height() - client_rect.bottom;
    var distance_from_left = client_rect.left;
    var distance_from_right = message_viewport.width() - client_rect.right;

    var elt_will_fit_horizontally =
        distance_from_left + elt.width() / 2 > popover_width / 2 &&
        distance_from_right + elt.width() / 2 > popover_width / 2;

    var elt_will_fit_vertically =
        distance_from_bottom + elt.height() / 2 > popover_height / 2 &&
        distance_from_top + elt.height() / 2 > popover_height / 2;

    // default to placing the popover in the center of the screen
    var placement = 'viewport_center';

    // prioritize left/right over top/bottom
    if (distance_from_top > popover_height && elt_will_fit_horizontally) {
        placement = 'top';
    }
    if (distance_from_bottom > popover_height && elt_will_fit_horizontally) {
        placement = 'bottom';
    }

    if (prefer_vertical_positioning && placement !== 'viewport_center') {
        // If vertical positioning is preferred and the popover fits in
        // either top or bottom position then return.
        return placement;
    }

    if (distance_from_left > popover_width && elt_will_fit_vertically) {
        placement = 'left';
    }
    if (distance_from_right > popover_width && elt_will_fit_vertically) {
        placement = 'right';
    }

    return placement;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = popovers;
}
