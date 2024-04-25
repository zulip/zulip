import $ from "jquery";
import assert from "minimalistic-assert";
import tippy from "tippy.js";

// You won't find every click handler here, but it's a good place to start!

import render_buddy_list_tooltip_content from "../templates/buddy_list_tooltip_content.hbs";

import * as activity_ui from "./activity_ui";
import * as browser_history from "./browser_history";
import * as buddy_data from "./buddy_data";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_reply from "./compose_reply";
import * as compose_state from "./compose_state";
import {media_breakpoints_num} from "./css_variables";
import * as emoji_picker from "./emoji_picker";
import * as hash_util from "./hash_util";
import * as hashchange from "./hashchange";
import * as message_edit from "./message_edit";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import * as navigate from "./navigate";
import {page_params} from "./page_params";
import * as pm_list from "./pm_list";
import * as popover_menus from "./popover_menus";
import * as reactions from "./reactions";
import * as recent_view_ui from "./recent_view_ui";
import * as rows from "./rows";
import * as server_events from "./server_events";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_preferences from "./settings_preferences";
import * as settings_toggle from "./settings_toggle";
import * as sidebar_ui from "./sidebar_ui";
import * as spectators from "./spectators";
import * as starred_messages_ui from "./starred_messages_ui";
import * as stream_list from "./stream_list";
import * as stream_popover from "./stream_popover";
import * as topic_list from "./topic_list";
import * as ui_util from "./ui_util";
import {parse_html} from "./ui_util";
import * as user_topics from "./user_topics";
import * as util from "./util";

export function initialize() {
    // MESSAGE CLICKING

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
            assert(message_lists.current !== undefined);
            message_lists.current.select_id(id);
            setTimeout(() => {
                // The algorithm to trigger long tap is that first, we check
                // whether the message is still touched after MS_DELAY ms and
                // the user isn't scrolling the messages(see other touch event
                // handlers to see how these meta variables are handled).
                // Later we check whether after MS_DELAY the user is still
                // long touching the same message as it can be possible that
                // user touched another message within MS_DELAY period.
                if (meta.touchdown === true && !meta.invalid && id === meta.current_target) {
                    $(this).trigger("longtap");
                }
            }, MS_DELAY);
        });

        $("#main_div").on("touchend", ".messagebox", () => {
            meta.touchdown = false;
        });

        $("#main_div").on("touchmove", ".messagebox", () => {
            meta.invalid = true;
        });

        $("#main_div").on("contextmenu", ".messagebox", (e) => {
            e.preventDefault();
        });
    }

    // this initializes the trigger that will give off the longtap event, which
    // there is no point in running if we are on desktop since this isn't a
    // standard event that we would want to support.
    if (util.is_mobile()) {
        initialize_long_tap();
    }

    function is_clickable_message_element($target) {
        // This function defines all the elements within a message
        // body that have UI behavior other than starting a reply.

        // Links should be handled by the browser.
        if ($target.closest("a").length > 0) {
            return true;
        }

        // Forms for message editing contain input elements
        if ($target.is("textarea") || $target.is("input")) {
            return true;
        }

        // Widget for adjusting the height of a message.
        if ($target.is("button.message_expander") || $target.is("button.message_condenser")) {
            return true;
        }

        // Inline image, video and twitter previews.
        if (
            $target.is("img.message_inline_image") ||
            $target.is("video") ||
            $target.is(".message_inline_video") ||
            $target.is("img.twitter-avatar")
        ) {
            return true;
        }

        // UI elements for triggering message editing or viewing edit history.
        if ($target.is("i.edit_message_button") || $target.is(".message_edit_notice")) {
            return true;
        }

        // For spoilers, allow clicking either the header or elements within it
        if ($target.is(".spoiler-header") || $target.parents(".spoiler-header").length > 0) {
            return true;
        }

        // Ideally, this should be done via ClipboardJS, but it doesn't support
        // feature of stopPropagation once clicked.
        // See https://github.com/zenorocha/clipboard.js/pull/475
        if ($target.is(".copy_codeblock") || $target.parents(".copy_codeblock").length > 0) {
            return true;
        }

        // Don't select message on clicking message control buttons.
        if ($target.parents(".message_controls").length > 0) {
            return true;
        }

        // Allow toggling of tasks in todo widget
        if (
            $target.is(".todo-widget label.checkbox") ||
            $target.parents(".todo-widget label.checkbox").length > 0
        ) {
            return true;
        }

        return false;
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

        if (document.getSelection().type === "Range") {
            // Drags on the message (to copy message text) shouldn't trigger a reply.
            return;
        }

        const $row = $(this).closest(".message_row");
        const id = rows.id($row);

        assert(message_lists.current !== undefined);
        message_lists.current.select_id(id);

        if (message_edit.is_editing(id)) {
            // Clicks on a message being edited shouldn't trigger a reply.
            return;
        }

        // Clicks on a message from search results should bring the
        // user to the message's near view instead of opening the
        // compose box.
        const current_filter = narrow_state.filter();
        if (current_filter !== undefined && !current_filter.supports_collapsing_recipients()) {
            const message = message_store.get(id);

            if (message === undefined) {
                // This might happen for locally echoed messages, for example.
                return;
            }
            window.location = hash_util.by_conversation_and_time_url(message);
            return;
        }

        if (page_params.is_spectator) {
            return;
        }
        compose_reply.respond_to_message({trigger: "message click"});
        e.stopPropagation();
    };

    // if on normal non-mobile experience, a `click` event should run the message
    // selection function which will open the compose box  and select the message.
    if (!util.is_mobile()) {
        $("#main_div").on("click", ".messagebox", select_message_function);
        // on the other hand, on mobile it should be done with a long tap.
    } else {
        $("#main_div").on("longtap", ".messagebox", function (e) {
            const sel = window.getSelection();
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

    $("#main_div").on("click", ".star_container", function (e) {
        e.stopPropagation();

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        const message_id = rows.id($(this).closest(".message_row"));
        const message = message_store.get(message_id);
        starred_messages_ui.toggle_starred_and_update_server(message);
    });

    $("#main_div").on("click", ".message_reaction", function (e) {
        e.stopPropagation();

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        emoji_picker.hide_emoji_popover();
        const local_id = $(this).attr("data-reaction-id");
        const message_id = rows.get_message_id(this);
        reactions.process_reaction_click(message_id, local_id);
        $(".tooltip").remove();
    });

    $("body").on("click", ".reveal_hidden_message", (e) => {
        assert(message_lists.current !== undefined);
        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        message_lists.current.view.reveal_hidden_message(message_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("#main_div").on("click", "a.stream", function (e) {
        e.preventDefault();
        // Note that we may have an href here, but we trust the stream id more,
        // so we re-encode the hash.
        const stream_id = Number.parseInt($(this).attr("data-stream-id"), 10);
        if (stream_id) {
            browser_history.go_to_location(hash_util.by_stream_url(stream_id));
            return;
        }
        window.location.href = $(this).attr("href");
    });

    $("body").on("click", "#scroll-to-bottom-button-clickable-area", (e) => {
        e.preventDefault();
        e.stopPropagation();

        navigate.to_end();
    });

    $("body").on("click", ".message_row", function () {
        $(".selected_msg_for_touchscreen").removeClass("selected_msg_for_touchscreen");
        $(this).addClass("selected_msg_for_touchscreen");
    });

    // MESSAGE EDITING

    $("body").on("click", ".edit_content_button", function (e) {
        assert(message_lists.current !== undefined);
        const $row = message_lists.current.get_row(rows.id($(this).closest(".message_row")));
        message_lists.current.select_id(rows.id($row));
        message_edit.start($row);
        e.stopPropagation();
    });
    $("body").on("click", ".move_message_button", function (e) {
        assert(message_lists.current !== undefined);
        const $row = message_lists.current.get_row(rows.id($(this).closest(".message_row")));
        const message_id = rows.id($row);
        const message = message_lists.current.get(message_id);
        stream_popover.build_move_topic_to_stream_popover(
            message.stream_id,
            message.topic,
            false,
            message,
        );
        e.stopPropagation();
    });
    $("body").on("click", ".always_visible_topic_edit,.on_hover_topic_edit", function (e) {
        const $recipient_row = $(this).closest(".recipient_row");
        message_edit.start_inline_topic_edit($recipient_row);
        e.stopPropagation();
    });
    $("body").on("click", ".topic_edit_save", function (e) {
        const $recipient_row = $(this).closest(".recipient_row");
        message_edit.try_save_inline_topic_edit($recipient_row);
        e.stopPropagation();
    });
    $("body").on("click", ".topic_edit_cancel", function (e) {
        const $recipient_row = $(this).closest(".recipient_row");
        message_edit.end_inline_topic_edit($recipient_row);
        e.stopPropagation();
    });
    $("body").on("click", ".message_edit_save", function (e) {
        const $row = $(this).closest(".message_row");
        message_edit.save_message_row_edit($row);
        e.stopPropagation();
    });
    $("body").on("click", ".message_edit_cancel", function (e) {
        const $row = $(this).closest(".message_row");
        message_edit.end_message_row_edit($row);
        e.stopPropagation();
    });
    $("body").on("click", ".message_edit_close", function (e) {
        const $row = $(this).closest(".message_row");
        message_edit.end_message_row_edit($row);
        e.stopPropagation();
    });
    $("body").on("click", "a", function () {
        if (document.activeElement === this) {
            ui_util.blur_active_element();
        }
    });
    $("body").on("click", ".message_edit_form .compose_upload_file", function (e) {
        e.preventDefault();

        const row_id = rows.id($(this).closest(".message_row"));
        $(`#edit_form_${CSS.escape(row_id)} .file_input`).trigger("click");
    });
    $("body").on("focus", ".message_edit_form .message_edit_content", (e) => {
        compose_state.set_last_focused_compose_type_input(e.target);
    });

    $("body").on("click", ".message_edit_form .markdown_preview", (e) => {
        e.preventDefault();
        const $row = rows.get_closest_row(e.target);
        const $msg_edit_content = $row.find(".message_edit_content");
        const content = $msg_edit_content.val();

        // Disable unneeded compose_control_buttons as we don't
        // need them in preview mode.
        $row.addClass("preview_mode");
        $row.find(".preview_mode_disabled .compose_control_button").attr("tabindex", -1);

        $msg_edit_content.hide();
        $row.find(".markdown_preview").hide();
        $row.find(".undo_markdown_preview").show();
        $row.find(".preview_message_area").show();

        compose.render_and_show_preview(
            $row.find(".markdown_preview_spinner"),
            $row.find(".preview_content"),
            content,
        );
    });

    $("body").on("click", ".message_edit_form .undo_markdown_preview", (e) => {
        e.preventDefault();
        const $row = rows.get_closest_row(e.target);

        // While in preview mode we disable unneeded compose_control_buttons,
        // so here we are re-enabling those compose_control_buttons
        $row.removeClass("preview_mode");
        $row.find(".preview_mode_disabled .compose_control_button").attr("tabindex", 0);

        $row.find(".message_edit_content").show();
        $row.find(".undo_markdown_preview").hide();
        $row.find(".preview_message_area").hide();
        $row.find(".preview_content").empty();
        $row.find(".markdown_preview").show();
    });

    // RESOLVED TOPICS
    $("body").on("click", ".message_header .on_hover_topic_resolve", (e) => {
        e.stopPropagation();
        const $recipient_row = $(e.target).closest(".recipient_row");
        const message_id = rows.id_for_recipient_row($recipient_row);
        const topic_name = $(e.target).attr("data-topic-name");
        message_edit.toggle_resolve_topic(message_id, topic_name, false, $recipient_row);
    });

    $("body").on("click", ".message_header .on_hover_topic_unresolve", (e) => {
        e.stopPropagation();
        const $recipient_row = $(e.target).closest(".recipient_row");
        const message_id = rows.id_for_recipient_row($recipient_row);
        const topic_name = $(e.target).attr("data-topic-name");
        message_edit.toggle_resolve_topic(message_id, topic_name, false, $recipient_row);
    });

    // Mute topic in a unmuted stream
    $("body").on("click", ".message_header .stream_unmuted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.MUTED,
        );
    });

    // Unmute topic in a unmuted stream
    $("body").on("click", ".message_header .stream_unmuted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    // Unmute topic in a muted stream
    $("body").on("click", ".message_header .stream_muted.on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.UNMUTED,
        );
    });

    // Mute topic in a muted stream
    $("body").on("click", ".message_header .stream_muted.on_hover_topic_mute", (e) => {
        e.stopPropagation();
        user_topics.set_visibility_policy_for_element(
            $(e.target),
            user_topics.all_visibility_policies.INHERIT,
        );
    });

    // RECIPIENT BARS

    function get_row_id_for_narrowing(narrow_link_elem) {
        const $group = rows.get_closest_group(narrow_link_elem);
        const msg_id = rows.id_for_recipient_row($group);

        assert(message_lists.current !== undefined);
        const nearest = message_lists.current.get(msg_id);
        const selected = message_lists.current.selected_message();
        if (util.same_recipient(nearest, selected)) {
            return selected.id;
        }
        return nearest.id;
    }

    $("#message_feed_container").on("click", ".narrows_by_recipient", function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_recipient(row_id, {trigger: "message header"});
    });

    $("#message_feed_container").on("click", ".narrows_by_topic", function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_topic(row_id, {trigger: "message header"});
    });

    // SIDEBARS
    $(".buddy-list-section").on("click", ".selectable_sidebar_block", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const $li = $(e.target).parents("li");

        activity_ui.narrow_for_user({$li});

        e.preventDefault();
        e.stopPropagation();
        sidebar_ui.hide_userlist_sidebar();
        $(".tooltip").remove();
    });

    // Doesn't show tooltip on touch devices.
    function do_render_buddy_list_tooltip(
        $elem,
        title_data,
        get_target_node,
        check_reference_removed,
        subtree = false,
        parent_element_to_append = null,
        is_custom_observer_needed = true,
    ) {
        let placement = "left";
        let observer;
        if (window.innerWidth < media_breakpoints_num.md) {
            // On small devices display tooltips based on available space.
            // This will default to "bottom" placement for this tooltip.
            placement = "auto";
        }
        tippy($elem[0], {
            // Quickly display and hide right sidebar tooltips
            // so that they don't stick and overlap with
            // each other.
            delay: 0,
            // Don't show tooltip on touch devices (99% mobile) since touch pressing on users in the left or right
            // sidebar leads to narrow being changed and the sidebar is hidden. So, there is no user displayed
            // to show tooltip for. It is safe to show the tooltip on long press but it not worth
            // the inconvenience of having a tooltip hanging around on a small mobile screen if anything going wrong.
            touch: false,
            content: () => parse_html(render_buddy_list_tooltip_content(title_data)),
            arrow: true,
            placement,
            showOnCreate: true,
            onHidden(instance) {
                instance.destroy();
                if (is_custom_observer_needed) {
                    observer.disconnect();
                }
            },
            onShow(instance) {
                if (!is_custom_observer_needed) {
                    return;
                }
                // We cannot use MutationObserver directly on the reference element because
                // it will be removed and we need to attach it on an element which will remain in the DOM.
                const target_node = get_target_node(instance);
                // We only need to know if any of the `li` elements were removed.
                const config = {attributes: false, childList: true, subtree};
                const callback = function (mutationsList) {
                    for (const mutation of mutationsList) {
                        // Hide instance if reference is in the removed node list.
                        if (check_reference_removed(mutation, instance)) {
                            popover_menus.hide_current_popover_if_visible(instance);
                        }
                    }
                };
                observer = new MutationObserver(callback);
                observer.observe(target_node, config);
            },
            appendTo: () => parent_element_to_append || document.body,
        });
    }

    // BUDDY LIST TOOLTIPS (not displayed on touch devices)
    $(".buddy-list-section").on("mouseenter", ".selectable_sidebar_block", (e) => {
        e.stopPropagation();
        const $elem = $(e.currentTarget).closest(".user_sidebar_entry").find(".user-presence-link");
        const user_id_string = $elem.attr("data-user-id");
        const title_data = buddy_data.get_title_data(user_id_string, false);

        // `target_node` is the `ul` element since it stays in DOM even after updates.
        function get_target_node() {
            return $(e.target).parents(".buddy-list-section")[0];
        }

        function check_reference_removed(mutation, instance) {
            return Array.prototype.includes.call(
                mutation.removedNodes,
                instance.reference.parentElement,
            );
        }

        do_render_buddy_list_tooltip(
            $elem.parent(),
            title_data,
            get_target_node,
            check_reference_removed,
        );

        /*
           The following implements a little tooltip giving the name for status emoji
           when hovering them in the right sidebar. This requires special logic, to avoid
           conflicting with the main tooltip or showing duplicate tooltips.
        */
        $(".user-presence-link .status-emoji-name").off("mouseenter").off("mouseleave");
        $(".user-presence-link .status-emoji-name").on("mouseenter", () => {
            const instance = $elem.parent()[0]._tippy;
            if (instance && instance.state.isVisible) {
                instance.destroy();
            }
        });
        $(".user-presence-link .status-emoji-name").on("mouseleave", () => {
            do_render_buddy_list_tooltip(
                $elem.parent(),
                title_data,
                get_target_node,
                check_reference_removed,
            );
        });
    });

    // DIRECT MESSAGE LIST TOOLTIPS (not displayed on touch devices)
    $("body").on("mouseenter", ".dm-user-status", (e) => {
        e.stopPropagation();
        const $elem = $(e.currentTarget);
        const user_ids_string = $elem.attr("data-user-ids-string");
        // This converts from 'true' in the DOM to true.
        const is_group = JSON.parse($elem.attr("data-is-group"));

        const title_data = buddy_data.get_title_data(user_ids_string, is_group);

        // Since anything inside `#left_sidebar_scroll_container` can be replaced, it is our target node here.
        function get_target_node() {
            return document.querySelector("#left_sidebar_scroll_container");
        }

        // Whole list is just replaced, so we need to check for that.
        function check_reference_removed(mutation, instance) {
            return Array.prototype.includes.call(
                mutation.removedNodes,
                $(instance.reference).parents(".dm-list")[0],
            );
        }

        const check_subtree = true;
        do_render_buddy_list_tooltip(
            $elem,
            title_data,
            get_target_node,
            check_reference_removed,
            check_subtree,
        );

        /*
           The following implements a little tooltip giving the name for status emoji
           when hovering them in the left sidebar. This requires special logic, to avoid
           conflicting with the main tooltip or showing duplicate tooltips.
        */
        $(".dm-user-status .status-emoji-name").off("mouseenter").off("mouseleave");
        $(".dm-user-status .status-emoji-name").on("mouseenter", () => {
            const instance = $elem[0]._tippy;
            if (instance && instance.state.isVisible) {
                instance.destroy();
            }
        });
        $(".dm-user-status .status-emoji-name").on("mouseleave", () => {
            do_render_buddy_list_tooltip(
                $elem,
                title_data,
                get_target_node,
                check_reference_removed,
            );
        });
    });

    // Recent conversations direct messages (Not displayed on small widths)
    $("body").on("mouseenter", ".recent_topic_stream .pm_status_icon", (e) => {
        e.stopPropagation();
        const $elem = $(e.currentTarget);
        const user_ids_string = $elem.attr("data-user-ids-string");
        // Don't show tooltip for group direct messages.
        if (!user_ids_string || user_ids_string.split(",").length !== 1) {
            return;
        }
        const title_data = recent_view_ui.get_pm_tooltip_data(user_ids_string);
        const noop = () => {};
        do_render_buddy_list_tooltip($elem, title_data, noop, noop, false, undefined, false);
    });

    // MISC

    {
        const sel = [
            "#stream_filters",
            "#left-sidebar-navigation-list",
            "#buddy-list-users-matching-view",
        ].join(", ");

        $(sel).on("click", "a", function () {
            this.blur();
        });
    }

    $("body").on("click", ".logout_button", () => {
        $("#logout_form").trigger("submit");
    });

    $(".restart_get_events_button").on("click", () => {
        server_events.restart_get_events({dont_block: true});
    });

    $("#settings_page").on("click", ".collapse-settings-btn", () => {
        settings_toggle.toggle_org_setting_collapse();
    });

    $("body").on("click", ".reload_link", () => {
        window.location.reload();
    });

    // COMPOSE

    $("body").on("click", ".empty_feed_compose_stream", (e) => {
        compose_actions.start({
            message_type: "stream",
            trigger: "empty feed message",
        });
        e.preventDefault();
    });
    $("body").on("click", ".empty_feed_compose_private", (e) => {
        compose_actions.start({
            message_type: "private",
            trigger: "empty feed message",
        });
        e.preventDefault();
    });

    $("body").on("click", "[data-overlay-trigger]", function () {
        const target = $(this).attr("data-overlay-trigger");
        browser_history.go_to_location(target);
    });

    function handle_compose_click(e) {
        const $target = $(e.target);
        // Emoji clicks should be handled by their own click handler in emoji_picker.js
        if ($target.is(".emoji_map, img.emoji, .drag, .compose_gif_icon, .compose_control_menu")) {
            return;
        }

        if ($target.is("#send_later i")) {
            // Since the click for this is handled by tippyjs, we cannot add stopPropagation
            // there without adding a special click event handler to show the popover,
            // so it is better just do it here.
            e.stopPropagation();
            return;
        }

        // The dropdown menu needs to process clicks to open and close.
        if ($target.parents("#compose_select_recipient_widget_wrapper").length > 0) {
            return;
        }

        // The mobile compose button has its own popover when clicked, so it already.
        // hides other popovers.
        if ($target.is(".compose_mobile_button, .compose_mobile_button *")) {
            return;
        }
    }

    $("body").on("click", "#compose-content", handle_compose_click);

    $("body").on("click", "#compose_close", () => {
        compose_actions.cancel();
    });

    $("body").on("focus", "#compose-textarea", (e) => {
        compose_state.set_last_focused_compose_type_input(e.target);
    });

    // LEFT SIDEBAR

    $("body").on("click", "#clear_search_topic_button", topic_list.clear_topic_search);

    $(".streams_filter_icon").on("click", (e) => {
        e.stopPropagation();
        stream_list.toggle_filter_displayed(e);
    });

    $("body").on(
        "click",
        ".direct-messages-container.zoom-out #private_messages_section_header",
        (e) => {
            if ($(e.target).closest("#show_all_private_messages").length === 1) {
                // Let the browser handle the "direct message feed" widget.
                return;
            }

            e.preventDefault();
            e.stopPropagation();
            const $left_sidebar_scrollbar = $(
                "#left_sidebar_scroll_container .simplebar-content-wrapper",
            );
            const scroll_position = $left_sidebar_scrollbar.scrollTop();

            if (stream_list.is_zoomed_in()) {
                stream_list.zoom_out();
            }

            // This next bit of logic is a bit subtle; this header
            // button scrolls to the top of the direct messages
            // section is uncollapsed but out of view; otherwise, we
            // toggle its collapsed state.
            if (scroll_position === 0 || pm_list.is_private_messages_collapsed()) {
                pm_list.toggle_private_messages_section();
            }
            $left_sidebar_scrollbar.scrollTop(0);
        },
    );

    /* The DIRECT MESSAGES label's click behavior is complicated;
     * only when zoomed in does it have a navigation effect, so we need
     * this click handler rather than just a link. */
    $("body").on(
        "click",
        ".direct-messages-container.zoom-in #private_messages_section_header",
        (e) => {
            e.preventDefault();
            e.stopPropagation();

            window.location.hash = "narrow/is/dm";
        },
    );

    // disable the draggability for left-sidebar components
    $("#stream_filters, #left-sidebar-navigation-list").on("dragstart", (e) => {
        e.target.blur();
        return false;
    });

    // Chrome focuses an element when dragging it which can be confusing when
    // users involuntarily drag something and we show them the focus outline.
    $("body").on("dragstart", "a", (e) => e.target.blur());

    // Don't focus links on middle click.
    $("body").on("mouseup", "a", (e) => {
        if (e.button === 1) {
            // middle click
            e.target.blur();
        }
    });

    // Don't focus links on context menu.
    $("body").on("contextmenu", "a", (e) => e.target.blur());

    $("body").on("click", ".language_selection_widget button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        settings_preferences.launch_default_language_setting_modal();
    });

    $("body").on("click", "#header-container .brand", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        hashchange.set_hash_to_home_view();
    });

    // MAIN CLICK HANDLER

    $(document).on("click", (e) => {
        if (e.button !== 0 || $(e.target).is(".drag")) {
            // Firefox emits right click events on the document, but not on
            // the child nodes, so the #compose stopPropagation doesn't get a
            // chance to capture right clicks.
            return;
        }

        if (compose_state.composing() && !$(e.target).parents("#compose").length) {
            if (
                $(e.target).closest("a").length > 0 ||
                $(e.target).closest(".copy_codeblock").length > 0
            ) {
                // Refocus compose message text box if one clicks an external
                // link/url to view something else while composing a message.
                // See issue #4331 for more details.
                //
                // We do the same when copying a code block, since the
                // most likely next action within Zulip is to paste it
                // into compose and modify it.
                $("textarea#compose-textarea").trigger("focus");
                return;
            } else if (
                !window.getSelection().toString() &&
                // Clicking any input or text area should not close
                // the compose box; this means using the sidebar
                // filters or search widgets won't unnecessarily close
                // compose.
                !$(e.target).closest("input").length &&
                !$(e.target).closest(".todo-widget label.checkbox").length &&
                !$(e.target).closest("textarea").length &&
                !$(e.target).closest("select").length &&
                // Clicks inside an overlay, popover, custom
                // modal, or backdrop of one of the above
                // should not have any effect on the compose
                // state.
                !$(e.target).closest(".overlay").length &&
                !$(e.target).closest(".micromodal").length &&
                !$(e.target).closest("[data-tippy-root]").length &&
                !$(e.target).closest(".typeahead").length &&
                !$(e.target).closest(".flatpickr-calendar").length &&
                $(e.target).closest("body").length
            ) {
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
    $(".dropdown-menu a").on("touchstart", (e) => {
        e.stopPropagation();
    });

    $(".settings-header.mobile .fa-chevron-left").on("click", () => {
        settings_panel_menu.mobile_deactivate_section();
    });

    $("body").on("click", ".trigger-natural-click", (e) => {
        // Jquery prevents default action on anchor for `trigger("click")`
        // so we need to use click on element to trigger the default action.
        e.currentTarget.click();
    });
}
