var click_handlers = (function () {

// We don't actually export anything yet; this is just for consistency.
var exports = {};

// You won't find every click handler here, but it's a good place to start!

$(function () {

    // MOUSE MOVING DETECTION
    var clicking = false;
    var mouse_moved = false;

    var meta = {};

    function mousedown() {
        mouse_moved = false;
        clicking = true;
    }

    function mousemove() {
        if (clicking) {
            mouse_moved = true;
        }
    }

    $("#main_div").on("mousedown", ".messagebox", mousedown);
    $("#main_div").on("mousemove", ".messagebox", mousemove);

    // MESSAGE CLICKING

    function is_clickable_message_element(target) {
        return target.is("a") || target.is("img.message_inline_image") || target.is("img.twitter-avatar") ||
            target.is("div.message_length_controller") || target.is("textarea") || target.is("input") ||
            target.is("i.edit_content_button");
    }

    $("#main_div").on("click", ".messagebox", function (e) {
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
        if (!(clicking && mouse_moved)) {
            // Was a click (not a click-and-drag).
            var row = $(this).closest(".message_row");
            var id = rows.id(row);

            if (message_edit.is_editing(id)) {
                // Clicks on a message being edited shouldn't trigger a reply.
                return;
            }

            current_msg_list.select_id(id);
            compose.respond_to_message({trigger: 'message click'});
            e.stopPropagation();
            popovers.hide_all();
        }
        mouse_moved = false;
        clicking = false;
    });

    function toggle_star(message_id) {
        // Update the message object pointed to by the various message
        // lists.
        var message = ui.find_message(message_id);

        unread_ui.mark_message_as_read(message);
        ui.update_starred(message.id, message.starred !== true);
        message_flags.send_starred([message], message.starred);
    }

    $("#main_div").on("click", ".star", function (e) {
        e.stopPropagation();
        popovers.hide_all();
        toggle_star(rows.id($(this).closest(".message_row")));
    });

    $("#main_div").on("click", ".message_reaction", function (e) {
        e.stopPropagation();
        var emoji_name = $(this).attr('data-emoji-name');
        var message_id = $(this).parent().attr('data-message-id');
        reactions.message_reaction_on_click(message_id, emoji_name);
    });

    $("#main_div").on("click", "a.stream", function (e) {
        e.preventDefault();
        var stream = stream_data.get_sub_by_id($(this).attr('data-stream-id'));
        if (stream) {
            window.location.href = '/#narrow/stream/' + hashchange.encodeHashComponent(stream.name);
            return;
        }
        window.location.href = $(this).attr('href');
    });

    // NOTIFICATION CLICK

    $('body').on('click', '.notification', function () {
        var payload = $(this).data("narrow");
        ui.change_tab_to('#home');
        narrow.activate(payload.raw_operators, payload.opts_notif);
    });

    // MESSAGE EDITING

    $('body').on('click', '.edit_content_button', function (e) {
        var row = current_msg_list.get_row(rows.id($(this).closest(".message_row")));
        current_msg_list.select_id(rows.id(row));
        message_edit.start(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $('body').on('click','.always_visible_topic_edit,.on_hover_topic_edit', function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        message_edit.start_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_save", function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        message_edit.save(recipient_row, true);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_cancel", function (e) {
        var recipient_row = $(this).closest(".recipient_row");
        current_msg_list.hide_edit_topic(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_save", function (e) {
        var row = $(this).closest(".message_row");
        message_edit.save(row, false);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_cancel", function (e) {
        var row = $(this).closest(".message_row");
        message_edit.end(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_close", function (e) {
        var row = $(this).closest(".message_row");
        message_edit.end(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", "a", function () {
        if (document.activeElement === this) {
            ui.blur_active_element();
        }
    });

    $(window).on("focus", function () {
        meta.focusing = true;
    });

    // MUTING

    $('body').on('click', '.on_hover_topic_mute', function (e) {
        e.stopPropagation();
        var stream_id = $(e.currentTarget).attr('data-stream-id');
        var topic = $(e.currentTarget).attr('data-topic-name');
        var stream = stream_data.get_sub_by_id(stream_id);
        stream_popover.topic_ops.mute(stream.name, topic);
    });

    // RECIPIENT BARS

    function get_row_id_for_narrowing(narrow_link_elem) {
        var group = rows.get_closest_group(narrow_link_elem);
        var msg_id = rows.id_for_recipient_row(group);

        var nearest = current_msg_list.get(msg_id);
        var selected = current_msg_list.selected_message();
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
        var row_id = get_row_id_for_narrowing(this);
        narrow.by_recipient(row_id, {trigger: 'message header'});
    });

    $("#home").on("click", ".narrows_by_subject", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        var row_id = get_row_id_for_narrowing(this);
        narrow.by_subject(row_id, {trigger: 'message header'});
    });

    // SIDEBARS

    $("#userlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var sidebarHidden = !$(".app-main .column-right").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            popovers.show_userlist_sidebar();
        }
    });

    $("#streamlist-toggle-button").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var sidebarHidden = !$(".app-main .column-left").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            stream_popover.show_streamlist_sidebar();
        }
    });

    $('#user_presences').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        var user_id = $(e.target).parents('li').attr('data-user-id');
        var email = people.get_person_from_user_id(user_id).email;

        narrow.by('pm-with', email, {select_first_unread: true, trigger: 'sidebar'});
        // The preventDefault is necessary so that clicking the
        // link doesn't jump us to the top of the page.
        e.preventDefault();
        // The stopPropagation is necessary so that we don't
        // see the following sequence of events:
        // 1. This click "opens" the composebox
        // 2. This event propagates to the body, which says "oh, hey, the
        //    composebox is open and you clicked out of it, you must want to
        //    stop composing!"
        e.stopPropagation();
        // Since we're stopping propagation we have to manually close any
        // open popovers.
        popovers.hide_all();
    });

    $('#group-pms').expectOne().on('click', '.selectable_sidebar_block', function (e) {
        var user_ids_string = $(e.target).parents('li').attr('data-user-ids');
        var emails = people.user_ids_string_to_emails_string(user_ids_string);
        narrow.by('pm-with', emails, {select_first_unread: true, trigger: 'sidebar'});
        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();
    });

    $("#subscriptions_table").on("click", ".exit, #subscription_overlay", function (e) {
        if (meta.focusing) {
            meta.focusing = false;
            return;
        }

        if ($(e.target).is(".exit, .exit-sign, #subscription_overlay, #subscription_overlay > .flex")) {
            subs.close();
        }
    });

    $("#drafts_table").on("click", ".exit, #draft_overlay", function (e) {
        if (meta.focusing) {
            meta.focusing = false;
            return;
        }

        if ($(e.target).is(".exit, .exit-sign, #draft_overlay, #draft_overlay > .flex")) {
            drafts.close();
        }
    });

    // HOME

    // Capture both the left-sidebar Home click and the tab breadcrumb Home
    $(document).on('click', ".home-link[data-name='home']", function (e) {
        ui.change_tab_to('#home');
        narrow.deactivate();
        // We need to maybe scroll to the selected message
        // once we have the proper viewport set up
        setTimeout(navigate.maybe_scroll_to_selected, 0);
        e.preventDefault();
    });

    // This is obsolete, I believe.
    $(".brand").on('click', function (e) {
        if (ui.home_tab_obscured()) {
            ui.change_tab_to('#home');
        } else {
            narrow.restore_home_state();
        }
        navigate.maybe_scroll_to_selected();
        e.preventDefault();
    });

    // MISC

    (function () {
        var sel = ["#group-pm-list", "#stream_filters", "#global_filters", "#user_presences"].join(", ");

        $(sel).on("click", "a", function () {
            this.blur();
        });
    }());

    popovers.register_click_handlers();
    stream_popover.register_click_handlers();
    notifications.register_click_handlers();

    $('body').on('click', '.logout_button', function () {
        $('#logout_form').submit();
    });

    $('.restart_get_events_button').click(function () {
        server_events.restart_get_events({dont_block: true});
    });


    // COMPOSE

    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.
    $('#send-status .send-status-close').click(
        function () { $('#send-status').stop(true).fadeOut(500); }
    );


    $('.compose_stream_button').click(function () {
        compose.start('stream', {trigger: 'new topic button'});
    });
    $('.compose_private_button').click(function () {
        compose.start('private');
    });

    $('.empty_feed_compose_stream').click(function (e) {
        compose.start('stream', {trigger: 'empty feed message'});
        e.preventDefault();
    });
    $('.empty_feed_compose_private').click(function (e) {
        compose.start('private', {trigger: 'empty feed message'});
        e.preventDefault();
    });

    $(".informational-overlays").click(function (e) {
        if ($(e.target).is(".informational-overlays, .exit")) {
            ui.hide_info_overlay();
        }
    });

    $("body").on("click", "[data-overlay-trigger]", function () {
        ui.show_info_overlay($(this).attr("data-overlay-trigger"));
    });

    function handle_compose_click(e) {
        // Emoji clicks should be handled by their own click handler in popover.js
        if ($(e.target).is("#emoji_map, .emoji_popover, .emoji_popover.inner, img.emoji, .drag")) {
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
        compose.cancel();
    });

    $("#join_unsub_stream").click(function (e) {
        e.preventDefault();
        e.stopPropagation();

        window.location.hash = "streams/all";
    });

    // FEEDBACK

    // Keep these 2 feedback bot triggers separate because they have to
    // propagate the event differently.
    $('.feedback').click(function () {
        compose.start('private', {private_message_recipient: 'feedback@zulip.com',
                                  trigger: 'feedback menu item'});

    });
    $('#feedback_button').click(function (e) {
        e.stopPropagation();
        popovers.hide_all();
        compose.start('private', {private_message_recipient: 'feedback@zulip.com',
                                  trigger: 'feedback button'});

    });


    // WEBATHENA

    $('#right-sidebar, #top_navbar').on('click', '.webathena_login', function (e) {
        $("#zephyr-mirror-error").hide();
        var principal = ["zephyr", "zephyr"];
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
                url:      "/accounts/webathena_kerberos_login/",
                data:     {cred: JSON.stringify(r.session)},
                success: function () {
                    $("#zephyr-mirror-error").hide();
                },
                error: function () {
                    $("#zephyr-mirror-error").show();
                },
            });
        });
        $('#settings-dropdown').dropdown("toggle");
        e.preventDefault();
        e.stopPropagation();
    });
    // End Webathena code

    // BANKRUPTCY

    $(".bankruptcy_button").click(function () {
        unread_ui.enable();
    });

    (function () {
        var map = {
            ".stream-description-editable": subs.change_stream_description,
            ".stream-name-editable": subs.change_stream_name,
        };

        // http://stackoverflow.com/questions/4233265/contenteditable-set-caret-at-the-end-of-the-text-cross-browser
        function place_caret_at_end(el) {
            el.focus();

            if (typeof window.getSelection !== "undefined"
                    && typeof document.createRange !== "undefined") {
                var range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                var sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            } else if (typeof document.body.createTextRange !== "undefined") {
                var textRange = document.body.createTextRange();
                textRange.moveToElementText(el);
                textRange.collapse(false);
                textRange.select();
            }
        }

        $(document).on("keydown", ".editable-section", function (e) {
            e.stopPropagation();
        });

        $(document).on("drop", ".editable-section", function () {
            return false;
        });

        $(document).on("input", ".editable-section", function () {
            // if there are any child nodes, inclusive of <br> which means you
            // have lines in your description or title, you're doing something
            // wrong.
            if (this.hasChildNodes()) {
                this.innerText = this.innerText;
                place_caret_at_end(this);
            }
        });

        $("body").on("click", "[data-make-editable]", function () {
            var selector = $(this).attr("data-make-editable");
            var edit_area = $(this).parent().find(selector);
            if (edit_area.attr("contenteditable") === "true") {
                $("[data-finish-editing='" + selector + "']").hide();
                edit_area.attr("contenteditable", false);
                edit_area.text(edit_area.attr("data-prev-text"));
                $(this).html("");
            } else {
                $("[data-finish-editing='" + selector + "']").show();

                edit_area.attr("data-prev-text", edit_area.text().trim())
                    .attr("contenteditable", true);

                place_caret_at_end(edit_area[0]);

                $(this).html("&times;");
            }
        });

        $("body").on("click", "[data-finish-editing]", function (e) {
            var selector = $(this).attr("data-finish-editing");
            if (map[selector]) {
                map[selector](e);
                $(this).hide();
                $(this).parent().find(selector).attr("contenteditable", false);
                $("[data-make-editable='" + selector + "']").html("");
            }
        });
    }());

    $('#yes-bankrupt').click(function () {
        pointer.fast_forward_pointer();
        $("#yes-bankrupt").hide();
        $("#no-bankrupt").hide();
        $(this).after($("<div>").addClass("alert alert-info settings_committed")
                      .text(i18n.t("Bringing you to your latest messages…")));
    });

    (function () {
        $("#main_div").on("click", ".message_inline_image a", function (e) {
            var img = e.target;
            var row = rows.id($(img).closest(".message_row"));
            var user = current_msg_list.get(row).sender_full_name;
            var $target = $(this);

            // prevent the link from opening in a new page.
            e.preventDefault();
            // prevent the message compose dialog from happening.
            e.stopPropagation();

            if ($target.parent().hasClass("youtube-video")) {
                ui.lightbox({
                    type: "youtube",
                    id: $target.data("id"),
                });
            } else {
                ui.lightbox({
                    type: "photo",
                    image: img,
                    user: user,
                });
            }
        });

        $("#overlay .exit, #overlay .image-preview").click(function (e) {
            if ($(e.target).is(".exit, .image-preview")) {
                ui.exit_lightbox_photo();
            }
            e.preventDefault();
            e.stopPropagation();
        });

        $("#overlay .download").click(function () {
          this.blur();
        });
    }());

    // MAIN CLICK HANDLER

    $(document).on('click', function (e) {
        if (e.button !== 0 || $(e.target).is(".drag")) {
            // Firefox emits right click events on the document, but not on
            // the child nodes, so the #compose stopPropagation doesn't get a
            // chance to capture right clicks.
            return;
        }

        // Dismiss popovers if the user has clicked outside them
        if ($('.popover-inner').has(e.target).length === 0) {
            popovers.hide_all();
        }

        // Unfocus our compose area if we click out of it. Don't let exits out
        // of modals or selecting text (for copy+paste) trigger cancelling.
        if (compose.composing() && !$(e.target).is("a") &&
            ($(e.target).closest(".modal").length === 0) &&
            window.getSelection().toString() === "" &&
            ($(e.target).closest('#emoji_map').length === 0)) {
            compose.cancel();
        }
    });

    // Workaround for Bootstrap issue #5900, which basically makes dropdowns
    // unclickable on mobile devices.
    // https://github.com/twitter/bootstrap/issues/5900
    $('a.dropdown-toggle, .dropdown-menu a').on('touchstart', function (e) {
        e.stopPropagation();
    });

    $("#settings_overlay_container .sidebar").on("click", "li[data-section]", function () {
        var $this = $(this);

        $("#settings_overlay_container .sidebar li").removeClass("active no-border");
            $this.addClass("active");
        $this.prev().addClass("no-border");
    });

    $("#settings_overlay_container .sidebar").on("click", "li[data-section]", function () {
        var $this = $(this);
        var section = $this.data("section");
        var sel = "[data-name='" + section + "']";

        $("#settings_overlay_container .sidebar li").removeClass("active no-border");
        $this.addClass("active");
        $this.prev().addClass("no-border");

        if ($this.hasClass("admin")) {
            window.location.hash = "administration/" + section;
        } else {
            window.location.hash = "settings/" + section;
        }

        $(".settings-section, .settings-wrapper").removeClass("show");
        $(".settings-section" + sel + ", .settings-wrapper" + sel).addClass("show");
    });

    $("#settings_overlay_container").on("click", function (e) {
        var $target = $(e.target);
        if ($target.is(".exit-sign, .exit")) {
            hashchange.exit_settings();
        }
    });

    (function () {
        var settings_toggle = components.toggle({
            name: "settings-toggle",
            values: [
                { label: "Settings", key: "settings" },
                { label: "Administration", key: "administration" },
            ],
            callback: function (name, key) {
                $(".sidebar li").hide();

                if (key === "administration") {
                    $("li.admin").show();
                    $("li[data-section='organization-settings']").click();
                } else {
                    $("li:not(.admin)").show();
                    $("li[data-section='your-account']").click();
                }
            },
        }).get();

        $("#settings_overlay_container .tab-container")
            .append(settings_toggle);
    }());
});

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = click_handlers;
}
