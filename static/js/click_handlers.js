const util = require("./util");
// You won't find every click handler here, but it's a good place to start!

const render_buddy_list_tooltip = require('../templates/buddy_list_tooltip.hbs');
const render_buddy_list_tooltip_content = require('../templates/buddy_list_tooltip_content.hbs');

exports.initialize = function () {

    // MOUSE MOVING VS DRAGGING FOR SELECTION DATA TRACKING

    const drag = (function () {
        let start;
        let time;

        return {
            start: function (e) {
                start = { x: e.offsetX, y: e.offsetY };
                time = new Date().getTime();
            },

            end: function (e) {
                const end = { x: e.offsetX, y: e.offsetY };

                let dist;
                if (start) {
                    // get the linear difference between two coordinates on the screen.
                    dist = Math.sqrt(Math.pow(end.x - start.x, 2) + Math.pow(end.y - start.y, 2));
                } else {
                    // this usually happens if someone started dragging from outside of
                    // a message and finishes their drag inside the message. The intent
                    // in that case is clearly to select an area, not click a message;
                    // setting dist to Infinity here will ensure that.
                    dist = Infinity;
                }

                this.val = dist;
                this.time = new Date().getTime() - time;

                start = undefined;

                return dist;
            },
            val: null,
        };
    }());

    $("#main_div").on("mousedown", ".messagebox", function (e) {
        drag.start(e);
    });
    $("#main_div").on("mouseup", ".messagebox", function (e) {
        drag.end(e);
    });

    // MESSAGE CLICKING

    function is_clickable_message_element(target) {
        return target.is("a") || target.is("img.message_inline_image") || target.is("img.twitter-avatar") ||
            target.is("div.message_length_controller") || target.is("textarea") || target.is("input") ||
            target.is("i.edit_content_button") ||
            target.is(".highlight") && target.parent().is("a");
    }

    function initialize_long_tap() {
        const MS_DELAY = 750;
        const meta = {
            touchdown: false,
            current_target: undefined,
        };

        $("#main_div").on("touchstart", ".messagebox", function () {
            meta.touchdown = true;
            meta.invalid = false;
            const id = rows.id($(this).closest(".message_row"));
            meta.current_target = id;
            if (!id) {
                return;
            }
            current_msg_list.select_id(id);
            setTimeout(function () {
                // The algorithm to trigger long tap is that first, we check
                // whether the message is still touched after MS_DELAY ms and
                // the user isn't scrolling the messages(see other touch event
                // handlers to see how these meta variables are handled).
                // Later we check whether after MS_DELAY the user is still
                // long touching the same message as it can be possible that
                // user touched another message within MS_DELAY period.
                if (meta.touchdown === true && !meta.invalid) {
                    if (id === meta.current_target) {
                        $(this).trigger("longtap");
                    }
                }
            }.bind(this), MS_DELAY);
        });

        $("#main_div").on("touchend", ".messagebox", function () {
            meta.touchdown = false;
        });

        $("#main_div").on("touchmove", ".messagebox", function () {
            meta.invalid = true;
        });

        $("#main_div").on("contextmenu", ".messagebox", function (e) {
            e.preventDefault();
        });
    }

    // this initializes the trigger that will give off the longtap event, which
    // there is no point in running if we are on desktop since this isn't a
    // standard event that we would want to support.
    if (util.is_mobile()) {
        initialize_long_tap();
    }

    const select_message_function = function (e) {
        if (is_clickable_message_element($(e.target))) {
            // If this click came from a hyperlink, don't trigger the
            // reply action.  The simple way of doing this is simply
            // to call e.stopPropagation() from within the link's
            // click handler.
            //
            // Unfortunately, on Firefox, this breaks Ctrl-click and
            // Shift-click, because those are (apparently) implemented
            // by adding an event listener on link clicks, and
            // stopPropagation prevents them from being called.
            return;
        }

        if ($(e.target).is(".message_edit_notice")) {
            return;
        }

        // A tricky issue here is distinguishing hasty clicks (where
        // the mouse might still move a few pixels between mouseup and
        // mousedown) from selecting-for-copy.  We handle this issue
        // by treating it as a click if distance is very small
        // (covering the long-click case), or fairly small and over a
        // short time (covering the hasty click case).  This seems to
        // work nearly perfectly.  Once we no longer need to support
        // older browsers, we may be able to use the window.selection
        // API instead.
        if (drag.val < 5 && drag.time < 150 || drag.val < 2) {
            const row = $(this).closest(".message_row");
            const id = rows.id(row);

            if (message_edit.is_editing(id)) {
                // Clicks on a message being edited shouldn't trigger a reply.
                return;
            }

            current_msg_list.select_id(id);
            compose_actions.respond_to_message({trigger: 'message click'});
            e.stopPropagation();
            popovers.hide_all();
        }
    };

    // if on normal non-mobile experience, a `click` event should run the message
    // selection function which will open the compose box  and select the message.
    if (!util.is_mobile()) {
        $("#main_div").on("click", ".messagebox", select_message_function);
    // on the other hand, on mobile it should be done with a long tap.
    } else {
        $("#main_div").on("longtap", ".messagebox", function (e) {
            // find the correct selection API for the browser.
            const sel = window.getSelection ? window.getSelection() : document.selection;
            // if one matches, remove the current selections.
            // after a longtap that is valid, there should be no text selected.
            if (sel) {
                if (sel.removeAllRanges) {
                    sel.removeAllRanges();
                } else if (sel.empty) {
                    sel.empty();
                }
            }

            select_message_function.call(this, e);
        });
    }

    $("#main_div").on("click", ".star", function (e) {
        e.stopPropagation();
        popovers.hide_all();

        const message_id = rows.id($(this).closest(".message_row"));
        const message = message_store.get(message_id);
        message_flags.toggle_starred_and_update_server(message);
    });

    $("#main_div").on("click", ".message_reaction", function (e) {
        e.stopPropagation();
        const local_id = $(this).attr('data-reaction-id');
        const message_id = rows.get_message_id(this);
        reactions.process_reaction_click(message_id, local_id);
        $(".tooltip").remove();
    });

    $('body').on('mouseenter', '.message_edit_notice', function (e) {
        if (page_params.realm_allow_edit_history) {
            $(e.currentTarget).addClass("message_edit_notice_hover");
        }
    });

    $('body').on('mouseleave', '.message_edit_notice', function (e) {
        if (page_params.realm_allow_edit_history) {
            $(e.currentTarget).removeClass("message_edit_notice_hover");
        }
    });

    $('body').on('click', '.message_edit_notice', function (e) {
        popovers.hide_all();
        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        const row = current_msg_list.get_row(message_id);
        const message = current_msg_list.get(rows.id(row));
        const message_history_cancel_btn = $('#message-history-cancel');

        if (page_params.realm_allow_edit_history) {
            message_edit.show_history(message);
            message_history_cancel_btn.focus();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    // TOOLTIP FOR MESSAGE REACTIONS

    $('#main_div').on('mouseenter', '.message_reaction', function (e) {
        e.stopPropagation();
        const elem = $(e.currentTarget);
        const local_id = elem.attr('data-reaction-id');
        const message_id = rows.get_message_id(e.currentTarget);
        const title = reactions.get_reaction_title_data(message_id, local_id);

        elem.tooltip({
            title: title,
            trigger: 'hover',
            placement: 'bottom',
            animation: false,
        });
        elem.tooltip('show');
        $(".tooltip, .tooltip-inner").css('max-width', "600px");
        // Remove the arrow from the tooltip.
        $(".tooltip-arrow").remove();
    });

    $('#main_div').on('mouseleave', '.message_reaction', function (e) {
        e.stopPropagation();
        $(e.currentTarget).tooltip('destroy');
    });

    // DESTROY PERSISTING TOOLTIPS ON HOVER

    $("body").on('mouseenter', '.tooltip', function (e) {
        e.stopPropagation();
        $(e.currentTarget).remove();
    });

    $("#main_div").on("click", "a.stream", function (e) {
        e.preventDefault();
        // Note that we may have an href here, but we trust the stream id more,
        // so we re-encode the hash.
        const stream_id = parseInt($(this).attr('data-stream-id'), 10);
        if (stream_id) {
            hashchange.go_to_location(hash_util.by_stream_uri(stream_id));
            return;
        }
        window.location.href = $(this).attr('href');
    });

    // USER STATUS MODAL

    $(".user-status-value").on("click", function (e) {
        e.stopPropagation();
        const user_status_value = $(e.currentTarget).attr("data-user-status-value");
        $("input.user_status").val(user_status_value);
        user_status_ui.toggle_clear_message_button();
        user_status_ui.update_button();
    });

    // NOTIFICATION CLICK

    $('body').on('click', '.notification', function () {
        const payload = $(this).data("narrow");
        ui_util.change_tab_to('#home');
        narrow.activate(payload.raw_operators, payload.opts_notif);
    });

    // MESSAGE EDITING

    $('body').on('click', '.edit_content_button', function (e) {
        const row = current_msg_list.get_row(rows.id($(this).closest(".message_row")));
        current_msg_list.select_id(rows.id(row));
        message_edit.start(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $('body').on('click', '.always_visible_topic_edit,.on_hover_topic_edit', function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        message_edit.start_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_save", function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        message_edit.show_topic_edit_spinner(recipient_row);
        message_edit.save(recipient_row, true);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_cancel", function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        current_msg_list.hide_edit_topic_on_recipient_row(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_save", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.save(row, false);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_cancel", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.end(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_close", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.end(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".copy_message", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.end(row);
        row.find(".alert-msg").text(i18n.t("Copied!"));
        row.find(".alert-msg").css("display", "block");
        row.find(".alert-msg").delay(1000).fadeOut(300);
        e.preventDefault();
        e.stopPropagation();
    });
    $("body").on("click", "a", function () {
        if (document.activeElement === this) {
            ui_util.blur_active_element();
        }
    });
    $('#message_edit_form .send-status-close').click(function () {
        const row_id = rows.id($(this).closest(".message_row"));
        const send_status = $('#message-edit-send-status-' + row_id);
        $(send_status).stop(true).fadeOut(200);
    });
    $("body").on("click", "#message_edit_form [id^='attach_files_']", function (e) {
        e.preventDefault();

        const row_id = rows.id($(this).closest(".message_row"));
        $("#message_edit_file_input_" + row_id).trigger("click");
    });

    $("body").on("click", "#message_edit_form [id^='markdown_preview_']", function (e) {
        e.preventDefault();

        const row_id = rows.id($(this).closest(".message_row"));
        function $_(selector) {
            return $(selector + "_" + row_id);
        }

        const content = $_("#message_edit_content").val();
        $_("#message_edit_content").hide();
        $_("#markdown_preview").hide();
        $_("#undo_markdown_preview").show();
        $_("#preview_message_area").show();

        compose.render_and_show_preview($_("#markdown_preview_spinner"), $_("#preview_content"), content);
    });

    $("body").on("click", "#message_edit_form [id^='undo_markdown_preview_']", function (e) {
        e.preventDefault();

        const row_id = rows.id($(this).closest(".message_row"));
        function $_(selector) {
            return $(selector + "_" + row_id);
        }

        $_("#message_edit_content").show();
        $_("#undo_markdown_preview").hide();
        $_("#preview_message_area").hide();
        $_("#preview_content").empty();
        $_("#markdown_preview").show();
    });

    // MUTING

    $('body').on('click', '.on_hover_topic_mute', function (e) {
        e.stopPropagation();
        const stream_id = parseInt($(e.currentTarget).attr('data-stream-id'), 10);
        const topic = $(e.currentTarget).attr('data-topic-name');
        muting_ui.mute(stream_id, topic);
    });

    // RECIPIENT BARS

    function get_row_id_for_narrowing(narrow_link_elem) {
        const group = rows.get_closest_group(narrow_link_elem);
        const msg_id = rows.id_for_recipient_row(group);

        const nearest = current_msg_list.get(msg_id);
        const selected = current_msg_list.selected_message();
        if (util.same_recipient(nearest, selected)) {
            return selected.id;
        }
        return nearest.id;
    }

    $("#home").on("click", ".narrows_by_recipient", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_recipient(row_id, {trigger: 'message header'});
    });

    $("#home").on("click", ".narrows_by_topic", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_topic(row_id, {trigger: 'message header'});
    });

    // SIDEBARS

    $("#userlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-right").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            popovers.show_userlist_sidebar();
        }
    });

    $("#streamlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-left").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            stream_popover.show_streamlist_sidebar();
        }
    });

    $('#user_presences').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        const li = $(e.target).parents('li');

        activity.narrow_for_user({li: li});

        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();
        $(".tooltip").remove();
    });

    $('#group-pms').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        const user_ids_string = $(e.target).parents('li').attr('data-user-ids');
        const emails = people.user_ids_string_to_emails_string(user_ids_string);
        narrow.by('pm-with', emails, {trigger: 'sidebar'});
        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();
        $(".tooltip").remove();
    });

    $("#subscriptions_table").on("click", ".exit, #subscription_overlay", function (e) {
        if ($(e.target).is(".exit, .exit-sign, #subscription_overlay, #subscription_overlay > .flex")) {
            subs.close();
        }
    });

    function do_render_buddy_list_tooltip(elem, title_data) {
        elem.tooltip({
            template: render_buddy_list_tooltip(),
            title: render_buddy_list_tooltip_content(title_data),
            html: true,
            trigger: 'hover',
            placement: 'bottom',
            animation: false,
        });
        elem.tooltip('show');

        $(".tooltip").css('left', elem.pageX + 'px');
        $(".tooltip").css('top', elem.pageY + 'px');
    }

    // BUDDY LIST TOOLTIPS
    $('#user_presences').on('mouseenter', '.user-presence-link, .user_sidebar_entry .user_circle, .user_sidebar_entry .selectable_sidebar_block', function (e) {
        e.stopPropagation();
        const elem = $(e.currentTarget).closest(".user_sidebar_entry").find(".user-presence-link");
        const user_id_string = elem.attr('data-user-id');
        const title_data = buddy_data.get_title_data(user_id_string, false);
        do_render_buddy_list_tooltip(elem, title_data);
    });

    $('#user_presences').on('mouseleave click', '.user-presence-link, .user_sidebar_entry .user_circle, .user_sidebar_entry .selectable_sidebar_block', function (e) {
        e.stopPropagation();
        const elem = $(e.currentTarget).closest(".user_sidebar_entry").find(".user-presence-link");
        $(elem).tooltip('destroy');
    });

    // PM LIST TOOLTIPS
    $("body").on('mouseenter', '#pm_user_status, #group_pms_right_sidebar', function (e) {
        $(".tooltip").remove();
        e.stopPropagation();
        const elem = $(e.currentTarget);
        const user_ids_string = elem.attr('data-user-ids-string');
        // This converts from 'true' in the DOM to true.
        const is_group = JSON.parse(elem.attr('data-is-group'));

        const title_data = buddy_data.get_title_data(user_ids_string, is_group);
        do_render_buddy_list_tooltip(elem, title_data);
    });

    $("body").on('mouseleave', '#pm_user_status, #group_pms_right_sidebar', function (e) {
        e.stopPropagation();
        $(e.currentTarget).tooltip('destroy');
    });

    // HOME

    $(document).on('click', ".top_left_all_messages", function (e) {
        ui_util.change_tab_to('#home');
        narrow.deactivate();
        search.update_button_visibility();
        // We need to maybe scroll to the selected message
        // once we have the proper viewport set up
        setTimeout(navigate.maybe_scroll_to_selected, 0);
        e.preventDefault();
    });

    $(".brand").on('click', function (e) {
        if (overlays.is_active()) {
            overlays.close_active();
        } else {
            narrow.restore_home_state();
        }
        navigate.maybe_scroll_to_selected();
        e.preventDefault();
    });

    // MISC

    (function () {
        const sel = ["#group-pm-list", "#stream_filters", "#global_filters", "#user_presences"].join(", ");

        $(sel).on("click", "a", function () {
            this.blur();
        });
    }());

    popovers.register_click_handlers();
    emoji_picker.register_click_handlers();
    stream_popover.register_click_handlers();
    notifications.register_click_handlers();

    $('body').on('click', '.logout_button', function () {
        $('#logout_form').submit();
    });

    $('.restart_get_events_button').click(function () {
        server_events.restart_get_events({dont_block: true});
    });

    // this will hide the alerts that you click "x" on.
    $("body").on("click", ".alert-box > div .exit", function () {
        const $alert = $(this).closest(".alert-box > div");
        $alert.addClass("fade-out");
        setTimeout(function () {
            $alert.removeClass("fade-out show");
        }, 300);
    });

    $("#settings_page").on("click", ".collapse-settings-btn", function () {
        settings_toggle.toggle_org_setting_collapse();
    });

    $(".alert-box").on("click", ".stackframe .expand", function () {
        $(this).parent().siblings(".code-context").toggle("fast");
    });

    // COMPOSE

    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.
    $('#compose-send-status .compose-send-status-close').click(
        function () { $('#compose-send-status').stop(true).fadeOut(500); }
    );
    $('#nonexistent_stream_reply_error .compose-send-status-close').click(
        function () { $('#nonexistent_stream_reply_error').stop(true).fadeOut(500); }
    );


    $('.compose_stream_button').click(function () {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start('stream', {trigger: 'new topic button'});
    });
    $('.compose_private_button').click(function () {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start('private');
    });

    $('body').on('click', '.compose_mobile_stream_button', function () {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start('stream', {trigger: 'new topic button'});
    });
    $('body').on('click', '.compose_mobile_private_button', function () {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start('private');
    });

    $('.compose_reply_button').click(function () {
        compose_actions.respond_to_message({trigger: 'reply button'});
    });

    $('.empty_feed_compose_stream').click(function (e) {
        compose_actions.start('stream', {trigger: 'empty feed message'});
        e.preventDefault();
    });
    $('.empty_feed_compose_private').click(function (e) {
        compose_actions.start('private', {trigger: 'empty feed message'});
        e.preventDefault();
    });

    $("body").on("click", "[data-overlay-trigger]", function () {
        const target = $(this).attr("data-overlay-trigger");
        info_overlay.show(target);
    });

    function handle_compose_click(e) {
        // Emoji clicks should be handled by their own click handler in emoji_picker.js
        if ($(e.target).is("#emoji_map, img.emoji, .drag")) {
            return;
        }

        // The mobile compose button has its own popover when clicked, so it already.
        // hides other popovers.
        if ($(e.target).is(".compose_mobile_button, .compose_mobile_button *")) {
            return;
        }

        // Don't let clicks in the compose area count as
        // "unfocusing" our compose -- in other words, e.g.
        // clicking "Press enter to send" should not
        // trigger the composebox-closing code above.
        // But do allow our formatting link.
        if (!$(e.target).is("a")) {
            e.stopPropagation();
        }
        // Still hide the popovers, however
        popovers.hide_all();
    }

    $("#compose_buttons").click(handle_compose_click);
    $(".compose-content").click(handle_compose_click);

    $("#compose_close").click(function () {
        compose_actions.cancel();
    });

    $("#streams_inline_cog").click(function (e) {
        e.stopPropagation();
        hashchange.go_to_location('streams/subscribed');
    });

    $("#streams_filter_icon").click(function (e) {
        e.stopPropagation();
        stream_list.toggle_filter_displayed(e);
    });

    // WEBATHENA

    $('body').on('click', '.webathena_login', function (e) {
        $("#zephyr-mirror-error").removeClass("show");
        const principal = ["zephyr", "zephyr"];
        WinChan.open({
            url: "https://webathena.mit.edu/#!request_ticket_v1",
            relay_url: "https://webathena.mit.edu/relay.html",
            params: {
                realm: "ATHENA.MIT.EDU",
                principal: principal,
            },
        }, function (err, r) {
            if (err) {
                blueslip.warn(err);
                return;
            }
            if (r.status !== "OK") {
                blueslip.warn(r);
                return;
            }

            channel.post({
                url: "/accounts/webathena_kerberos_login/",
                data: {cred: JSON.stringify(r.session)},
                success: function () {
                    $("#zephyr-mirror-error").removeClass("show");
                },
                error: function () {
                    $("#zephyr-mirror-error").addClass("show");
                },
            });
        });
        $('#settings-dropdown').dropdown("toggle");
        e.preventDefault();
        e.stopPropagation();
    });
    // End Webathena code

    // disable the draggability for left-sidebar components
    $('#stream_filters, #global_filters').on('dragstart', function () {
        return false;
    });

    (function () {
        const map = {
            ".stream-description-editable": {
                on_start: stream_edit.set_raw_description,
                on_save: stream_edit.change_stream_description,
            },
            ".stream-name-editable": {
                on_start: null,
                on_save: stream_edit.change_stream_name,
            },
        };

        $(document).on("keydown", ".editable-section", function (e) {
            e.stopPropagation();
            // Cancel editing description if Escape key is pressed.
            if (e.which === 27) {
                $("[data-finish-editing='.stream-description-editable']").hide();
                $(this).attr("contenteditable", false);
                $(this).text($(this).attr("data-prev-text"));
                $("[data-make-editable]").html("");
            } else if (e.which === 13) {
                $(this).siblings(".checkmark").click();
            }
        });

        $(document).on("drop", ".editable-section", function () {
            return false;
        });

        $(document).on("input", ".editable-section", function () {
            // if there are any child nodes, inclusive of <br> which means you
            // have lines in your description or title, you're doing something
            // wrong.
            for (let x = 0; x < this.childNodes.length; x += 1) {
                if (this.childNodes[x].nodeType !== 3) {
                    this.innerText = this.innerText.replace(/\n/, "");
                    break;
                }
            }
        });

        $("body").on("click", "[data-make-editable]", function () {
            const selector = $(this).attr("data-make-editable");
            const edit_area = $(this).parent().find(selector);
            $(selector).removeClass("stream-name-edit-box");
            if (edit_area.attr("contenteditable") === "true") {
                $("[data-finish-editing='" + selector + "']").hide();
                edit_area.attr("contenteditable", false);
                edit_area.text(edit_area.attr("data-prev-text"));
                $(this).html("");
            } else {
                $("[data-finish-editing='" + selector + "']").show();

                $(selector).addClass("stream-name-edit-box");
                edit_area.attr("data-prev-text", edit_area.text().trim())
                    .attr("contenteditable", true);

                if (map[selector].on_start) {
                    map[selector].on_start(this, edit_area);
                }

                ui_util.place_caret_at_end(edit_area[0]);

                $(this).html("&times;");
            }
        });

        $("body").on("click", "[data-finish-editing]", function (e) {
            const selector = $(this).attr("data-finish-editing");
            $(selector).removeClass("stream-name-edit-box");
            if (map[selector].on_save) {
                map[selector].on_save(e);
                $(this).hide();
                $(this).parent().find(selector).attr("contenteditable", false);
                $("[data-make-editable='" + selector + "']").html("");
            }
        });
    }());


    // HOTSPOTS

    // open
    $('body').on('click', '.hotspot-icon', function (e) {
        // hide icon
        hotspots.close_hotspot_icon(this);

        // show popover
        const hotspot_name = $(e.target).closest('.hotspot-icon')
            .attr('id')
            .replace('hotspot_', '')
            .replace('_icon', '');
        const overlay_name = 'hotspot_' + hotspot_name + '_overlay';

        overlays.open_overlay({
            name: overlay_name,
            overlay: $('#' + overlay_name),
            on_close: function () {
                // close popover
                $(this).css({ display: 'block' });
                $(this).animate({ opacity: 1 }, {
                    duration: 300,
                });
            }.bind(this),
        });

        e.preventDefault();
        e.stopPropagation();
    });

    // confirm
    $('body').on('click', '.hotspot.overlay .hotspot-confirm', function (e) {
        e.preventDefault();
        e.stopPropagation();

        const overlay_name = $(this).closest('.hotspot.overlay').attr('id');

        const hotspot_name = overlay_name
            .replace('hotspot_', '')
            .replace('_overlay', '');

        // Comment below to disable marking hotspots as read in production
        hotspots.post_hotspot_as_read(hotspot_name);

        overlays.close_overlay(overlay_name);
        $('#hotspot_' + hotspot_name + '_icon').remove();
    });

    $('body').on('click', '.hotspot-button', function (e) {
        e.preventDefault();
        e.stopPropagation();

        hotspots.post_hotspot_as_read('intro_reply');
        hotspots.close_hotspot_icon($('#hotspot_intro_reply_icon'));
    });

    // stop propagation
    $('body').on('click', '.hotspot.overlay .hotspot-popover', function (e) {
        e.stopPropagation();
    });


    // MAIN CLICK HANDLER

    $(document).on('click', function (e) {
        if (e.button !== 0 || $(e.target).is(".drag")) {
            // Firefox emits right click events on the document, but not on
            // the child nodes, so the #compose stopPropagation doesn't get a
            // chance to capture right clicks.
            return;
        }

        // Dismiss popovers if the user has clicked outside them
        if ($('.popover-inner, #user-profile-modal, .emoji-info-popover, .app-main [class^="column-"].expanded').has(e.target).length === 0) {
            popovers.hide_all();
        }

        // If user clicks outside an active modal
        if ($('.modal.in').has(e.target).length === 0) {
            // Enable mouse events for the background as the modal closes
            $('.overlay.show').attr("style", null);
        }

        if (compose_state.composing()) {
            if ($(e.target).closest("a").length > 0) {
                // Refocus compose message text box if link is clicked
                $("#compose-textarea").focus();
                return;
            } else if (!window.getSelection().toString() &&
                       // Clicks inside an overlay, popover, custom
                       // modal, or backdrop of one of the above
                       // should not have any effect on the compose
                       // state.
                       !$(e.target).closest(".overlay").length &&
                       !$(e.target).closest('.popover').length &&
                       !$(e.target).closest(".modal").length &&
                       !$(e.target).closest(".modal-backdrop").length &&
                       $(e.target).closest('body').length) {
                // Unfocus our compose area if we click out of it. Don't let exits out
                // of overlays or selecting text (for copy+paste) trigger cancelling.
                // Check if the click is within the body to prevent extensions from
                // interfering with the compose box.
                compose_actions.cancel();
            }
        }
    });

    // Workaround for Bootstrap issue #5900, which basically makes dropdowns
    // unclickable on mobile devices.
    // https://github.com/twitter/bootstrap/issues/5900
    $('a.dropdown-toggle, .dropdown-menu a').on('touchstart', function (e) {
        e.stopPropagation();
    });

    $(".settings-header.mobile .fa-chevron-left").on("click", function () {
        $("#settings_page").find(".right").removeClass("show");
        $(this).parent().removeClass("slide-left");
    });

    // register navbar click handlers
    $('#search_exit').on("click", function (e) {
        tab_bar.exit_search();
        e.preventDefault();
        e.stopPropagation();
    });

    $(".search_open").on("click", function (e) {
        $('#search_query').typeahead('lookup').focus();
        e.preventDefault();
        e.stopPropagation();
    });
};

exports.bind_handler_for_opening_searchbox = function () {
    $(".search_closed").on("click", function (e) {
        tab_bar.open_search_bar_and_close_narrow_description();
        $('#search_query').select();
        e.preventDefault();
        e.stopPropagation();
    });
};

window.click_handlers = exports;
