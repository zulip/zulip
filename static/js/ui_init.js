const emojisets = require("./emojisets");
const markdown_config = require('./markdown_config');

// This is where most of our initialization takes place.
// TODO: Organize it a lot better.  In particular, move bigger
//       functions to other modules.

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

let current_message_hover;
function message_unhover() {
    if (current_message_hover === undefined) {
        return;
    }
    current_message_hover.find('span.edit_content').html("");
    current_message_hover = undefined;
}

function message_hover(message_row) {
    const id = rows.id(message_row);
    if (current_message_hover && rows.id(current_message_hover) === id) {
        return;
    }
    // Don't allow on-hover editing for local-only messages
    if (message_row.hasClass('local')) {
        return;
    }
    const message = current_msg_list.get(rows.id(message_row));
    message_unhover();
    current_message_hover = message_row;

    if (!message_edit.is_topic_editable(message)) {
        // The actions and reactions icon hover logic is handled entirely by CSS
        return;
    }

    // But the message edit hover icon is determined by whether the message is still editable
    if (message_edit.get_editability(message) === message_edit.editability_types.FULL &&
        !message.status_message) {
        message_row.find(".edit_content").html('<i class="fa fa-pencil edit_content_button" aria-hidden="true" title="Edit (e)"></i>');
    } else {
        message_row.find(".edit_content").html('<i class="fa fa-file-code-o edit_content_button" aria-hidden="true" title="View source (e)" data-message-id="' + id + '"></i>');
    }
}

exports.initialize_kitchen_sink_stuff = function () {
    // TODO:
    //      This function is a historical dumping ground
    //      for lots of miscellaneous setup.  Almost all of
    //      the code here can probably be moved to more
    //      specific-purpose modules like message_viewport.js.

    const throttled_mousewheelhandler = _.throttle(function (e, delta) {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta < 0) {
            if (message_viewport.at_top()) {
                navigate.up();
            }
        } else if (delta > 0) {
            if (message_viewport.at_bottom()) {
                navigate.down();
            }
        }

        message_viewport.set_last_movement_direction(delta);
    }, 50);

    message_viewport.message_pane.on('wheel', function (e) {
        const delta = e.originalEvent.deltaY;
        if (!overlays.is_active()) {
            // In the message view, we use a throttled mousewheel handler.
            throttled_mousewheelhandler(e, delta);
        }
        // If in a modal, we neither handle the event nor
        // preventDefault, allowing the modal to scroll normally.
    });

    $(window).resize(_.throttle(resize.handler, 50));

    // Scrolling in overlays. input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $('.modal-body, .scrolling_list, input, textarea').on('wheel', function (e) {
        const self = ui.get_scroll_element($(this));
        const scroll = self.scrollTop();
        const delta = e.originalEvent.deltaY;

        // The -1 fudge factor is important here due to rounding errors.  Better
        // to err on the side of not scrolling.
        const max_scroll = self.prop("scrollHeight") - self.innerHeight() - 1;

        e.stopPropagation();
        if (delta < 0 && scroll <= 0 ||
            delta > 0 && scroll >= max_scroll) {
            e.preventDefault();
        }
    });

    // Ignore wheel events in the compose area which weren't already handled above.
    $('#compose').on('wheel', function (e) {
        e.stopPropagation();
        e.preventDefault();
    });

    // A little hackish, because it doesn't seem to totally get us the
    // exact right width for the floating_recipient_bar and compose
    // box, but, close enough for now.
    resize.handler();

    if (!page_params.left_side_userlist) {
        $("#navbar-buttons").addClass("right-userlist");
    }

    if (page_params.high_contrast_mode) {
        $("body").addClass("high-contrast");
    }

    if (!page_params.dense_mode) {
        $("body").addClass("less_dense_mode");
    } else {
        $("body").addClass("more_dense_mode");
    }

    $("#main_div").on("mouseover", ".message_table .message_row", function () {
        const row = $(this).closest(".message_row");
        message_hover(row);
    });

    $("#main_div").on("mouseleave", ".message_table .message_row", function () {
        message_unhover();
    });

    $("#main_div").on("mouseover", ".sender_info_hover", function () {
        const row = $(this).closest(".message_row");
        row.addClass("sender_name_hovered");
    });

    $("#main_div").on("mouseout", ".sender_info_hover", function () {
        const row = $(this).closest(".message_row");
        row.removeClass("sender_name_hovered");
    });

    $("#main_div").on("mouseenter", ".youtube-video a", function () {
        $(this).addClass("fa fa-play");
    });

    $("#main_div").on("mouseleave", ".youtube-video a", function () {
        $(this).removeClass("fa fa-play");
    });

    $("#main_div").on("mouseenter", ".embed-video a", function () {
        const elem = $(this);
        // Set image height and css vars for play button position, if not done already
        const setPosition = !elem.data("entered-before");
        if (setPosition) {
            const imgW = elem.find("img")[0].width;
            const imgH = elem.find("img")[0].height;
            // Ensure height doesn't change on mouse enter
            elem.css("height", `${imgH}px`);
            // variables to set play button position
            const marginLeft = (imgW - 30) / 2;
            const marginTop = (imgH - 26) / 2;
            elem.css("--margin-left", `${marginLeft}px`)
                .css("--margin-top", `${marginTop}px`);
            elem.data("entered-before", true);
        }
        elem.addClass("fa fa-play");
    });

    $("#main_div").on("mouseleave", ".embed-video a", function () {
        $(this).removeClass("fa fa-play");
    });

    $("#subscriptions_table").on("mouseover", ".subscription_header", function () {
        $(this).addClass("active");
    });

    $("#subscriptions_table").on("mouseout", ".subscription_header", function () {
        $(this).removeClass("active");
    });

    $("#stream_message_recipient_stream").on('blur', function () {
        ui_util.decorate_stream_bar(this.value, $("#stream-message .message_header_stream"), true);
    });

    $(window).on('blur', function () {
        $(document.body).addClass('window_blurred');
    });

    $(window).on('focus', function () {
        $(document.body).removeClass('window_blurred');
    });

    $(document).on('message_selected.zulip', function (event) {
        if (current_msg_list !== event.msg_list) {
            return;
        }
        if (event.id === -1) {
            // If the message list is empty, don't do anything
            return;
        }
        const row = event.msg_list.get_row(event.id);
        $('.selected_message').removeClass('selected_message');
        row.addClass('selected_message');

        if (event.then_scroll) {
            if (row.length === 0) {
                const row_from_dom = current_msg_list.get_row(event.id);
                const messages = event.msg_list.all_messages();
                blueslip.debug("message_selected missing selected row", {
                    previously_selected: event.previously_selected,
                    selected_id: event.id,
                    selected_idx: event.msg_list.selected_idx(),
                    selected_idx_exact: messages.indexOf(event.msg_list.get(event.id)),
                    render_start: event.msg_list.view._render_win_start,
                    render_end: event.msg_list.view._render_win_end,
                    selected_id_from_idx: messages[event.msg_list.selected_idx()].id,
                    msg_list_sorted: _.isEqual(
                        messages.map(message => message.id),
                        _.chain(current_msg_list.all_messages()).pluck('id').clone().value().sort()
                    ),
                    found_in_dom: row_from_dom.length,
                });
            }
            if (event.target_scroll_offset !== undefined) {
                current_msg_list.view.set_message_offset(event.target_scroll_offset);
            } else {
                // Scroll to place the message within the current view;
                // but if this is the initial placement of the pointer,
                // just place it in the very center
                message_viewport.recenter_view(row,
                                               {from_scroll: event.from_scroll,
                                                force_center: event.previously_selected === -1});
            }
        }
    });

    $("#main_div").on("mouseenter", ".message_time", function (e) {
        const time_elem = $(e.target);
        const row = time_elem.closest(".message_row");
        const message = current_msg_list.get(rows.id(row));
        timerender.set_full_datetime(message, time_elem);
    });

    $('#streams_header h4').tooltip({placement: 'right',
                                     animation: false});

    $('#streams_header i[data-toggle="tooltip"]').tooltip({placement: 'left',
                                                           animation: false});

    $('#userlist-header #userlist-title').tooltip({placement: 'right',
                                                   animation: false});

    $('#userlist-header #user_filter_icon').tooltip({placement: 'left',
                                                     animation: false});

    $('.message_failed i[data-toggle="tooltip"]').tooltip();

    $('.copy_message[data-toggle="tooltip"]').tooltip();

    // We disable animations here because they can cause the tooltip
    // to change shape while fading away in weird way.
    $('#keyboard-icon').tooltip({animation: false});

    $("body").on("mouseover", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").show();
    });

    $("body").on("mouseout", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").hide();
    });

    $("body").on("mouseenter", ".copy_message", function () {
        $(this).show();
        $(this).tooltip('show');
    });

    $("body").on("mouseleave", ".copy_message", function () {
        $(this).tooltip('hide');
    });

    if (!page_params.realm_allow_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    if (page_params.realm_presence_disabled) {
        $("#user-list").hide();
    }
};

exports.initialize_everything = function () {
    /*
        When we initialize our various modules, a lot
        of them will consume data from the server
        in the form of `page_params`.

        The global `page_params` var is basically
        a massive dictionary with all the information
        that the client needs to run the app.  Here
        are some examples of what it includes:

            - all of the user's user-specific settings
            - all realm-specific settings that are
              pertinent to the user
            - info about streams/subscribers on the realm
            - realm settings
            - info about all the other users
            - some fairly dynamic data, like which of
              the other users are "present"

        Except for the actual Zulip messages, basically
        any data that you see in the app soon after page
        load comes from `page_params`.

        ## Mostly static data

        Now, we mostly leave `page_params` intact through
        the duration of the app.  Most of the data in
        `page_params` is fairly static in nature, and we
        will simply update it for basic changes like
        the following (meant as examples, not gospel):

            - I changed my 24-hour time preference.
            - The realm admin changed who can edit topics.
            - The team's realm icon has changed.
            - I switched from day mode to night mode.

        Especially for things that are settings-related,
        we rarely abstract away the data from `page_params`.
        As of this writing, over 90 modules refer directly
        to `page_params` for some reason or another.

        ## Dynamic data

        Some of the data in `page_params` is either
        more highly dynamic than settings data, or
        has more performance requirements than
        simple settings data, or both.  Examples
        include:

            - tracking all users (we want to have
              multiple Maps to find users, for example)
            - tracking all streams
            - tracking presence data
            - tracking user groups and bots
            - tracking recent PMs

        Using stream data as an example, we use a
        module called `stream_data` to actually track
        all the info about the streams that a user
        can know about.  We populate this module
        with data from `page_params`, but thereafter
        `stream_data.js` "owns" the stream data:

            - other modules should ask `stream_data`
              for stuff (and not go to `page_params`)
            - when server events come in, they should
              be processed by stream_data to update
              its own data structures

        To help enforce this paradigm, we do the
        following:

            - only pass `stream_data` what it needs
              from `page_params`
            - delete the reference to data owned by
              `stream_data` in `page_params` itself
    */

    function pop_fields(...fields) {
        const result = {};

        for (const field of fields) {
            result[field] = page_params[field];
            delete page_params[field];
        }

        return result;
    }

    const alert_words_params = pop_fields(
        'alert_words'
    );

    const bot_params = pop_fields(
        'realm_bots'
    );

    const people_params = pop_fields(
        'realm_users',
        'realm_non_active_users',
        'cross_realm_bots'
    );

    const pm_conversations_params = pop_fields(
        'recent_private_conversations'
    );

    const presence_params = pop_fields(
        'presences',
        'initial_servertime'
    );

    const stream_data_params = pop_fields(
        'subscriptions',
        'unsubscribed',
        'never_subscribed',
        'realm_default_streams'
    );

    const user_groups_params = pop_fields(
        'realm_user_groups'
    );

    const user_status_params = pop_fields(
        'user_status'
    );

    alert_words.initialize(alert_words_params);
    emojisets.initialize();
    people.initialize(page_params.user_id, people_params);
    scroll_bar.initialize();
    message_viewport.initialize();
    exports.initialize_kitchen_sink_stuff();
    echo.initialize();
    stream_color.initialize();
    stream_edit.initialize();
    stream_data.initialize(stream_data_params);
    pm_conversations.recent.initialize(pm_conversations_params);
    muting.initialize();
    subs.initialize();
    stream_list.initialize();
    condense.initialize();
    lightbox.initialize();
    click_handlers.initialize();
    copy_and_paste.initialize();
    overlays.initialize();
    invite.initialize();
    timerender.initialize();
    tab_bar.initialize();
    server_events.initialize();
    user_status.initialize(user_status_params);
    compose_pm_pill.initialize();
    search_pill_widget.initialize();
    reload.initialize();
    user_groups.initialize(user_groups_params);
    unread.initialize();
    bot_data.initialize(bot_params); // Must happen after people.initialize()
    message_fetch.initialize();
    message_scroll.initialize();
    emoji.initialize();
    markdown.initialize(
        page_params.realm_filters,
        markdown_config.get_helpers()
    );
    compose.initialize();
    composebox_typeahead.initialize(); // Must happen after compose.initialize()
    search.initialize();
    tutorial.initialize();
    notifications.initialize();
    gear_menu.initialize();
    settings_panel_menu.initialize();
    settings_sections.initialize();
    settings_toggle.initialize();
    pointer.initialize();
    unread_ui.initialize();
    presence.initialize(presence_params);
    activity.initialize();
    hashchange.initialize(); // Must happen after presence.initialize() and activity.initialize()
    emoji_picker.initialize();
    compose_fade.initialize();
    pm_list.initialize();
    topic_list.initialize();
    topic_zoom.initialize();
    drafts.initialize();
    sent_messages.initialize();
    hotspots.initialize();
    ui.initialize();
    panels.initialize();
    typing.initialize();
    starred_messages.initialize();
    user_status_ui.initialize();
};

$(function () {
    const finish = blueslip.start_timing('initialize_everything');
    exports.initialize_everything();
    finish();
});
