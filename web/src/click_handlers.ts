// You won't find every click handler here, but it's a good place to start!

import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_buddy_list_tooltip_content from "../templates/buddy_list_tooltip_content.hbs";

import * as activity_ui from "./activity_ui.ts";
import * as browser_history from "./browser_history.ts";
import * as buddy_data from "./buddy_data.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_reply from "./compose_reply.ts";
import * as compose_state from "./compose_state.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as hash_util from "./hash_util.ts";
import * as hashchange from "./hashchange.ts";
import * as message_edit from "./message_edit.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as narrow_state from "./narrow_state.ts";
import * as navigate from "./navigate.ts";
import {page_params} from "./page_params.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as reactions from "./reactions.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as rows from "./rows.ts";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as settings_toggle from "./settings_toggle.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as spectators from "./spectators.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_popover from "./stream_popover.ts";
import * as topic_list from "./topic_list.ts";
import * as ui_util from "./ui_util.ts";
import {parse_html} from "./ui_util.ts";
import * as util from "./util.ts";

export function initialize(): void {
    // MESSAGE CLICKING

    function initialize_long_tap(): void {
        const MS_DELAY = 750;
        const meta: {touchdown: boolean; current_target: number | undefined; invalid?: boolean} = {
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
                if (meta.touchdown && !meta.invalid && id === meta.current_target) {
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

    function is_clickable_message_element($target: JQuery<Element>): boolean {
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
            $target.is(".message_inline_animated_image_still") ||
            $target.is("video") ||
            $target.is(".message_inline_video") ||
            $target.is("img.twitter-avatar")
        ) {
            return true;
        }

        // UI elements for triggering message editing or viewing edit history.
        if (
            $target.is("i.edit_message_button") ||
            $target.is(".message_edit_notice") ||
            $target.is(".edit-notifications")
        ) {
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

    const select_message_function = function (this: HTMLElement, e: JQuery.TriggeredEvent): void {
        assert(e.target instanceof Element);
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

        if (document.getSelection()?.type === "Range") {
            // Drags on the message (to copy message text) shouldn't trigger a reply.
            return;
        }

        const $row = $(this).closest(".message_row");
        const id = rows.id($row);

        assert(message_lists.current !== undefined);
        message_lists.current.select_id(id);

        if (message_edit.currently_editing_messages.has(id)) {
            // Clicks on a message being edited shouldn't trigger a reply.
            return;
        }

        // Clicks on a message from search results should bring the
        // user to the message's near view instead of opening the
        // compose box.
        const current_filter = narrow_state.filter();
        if (current_filter !== undefined && !current_filter.contains_no_partial_conversations()) {
            const message = message_store.get(id);

            if (message === undefined) {
                // This might happen for locally echoed messages, for example.
                return;
            }
            window.location.href = hash_util.by_conversation_and_time_url(message);
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
        $("#main_div").on("longtap", ".messagebox", function (this: HTMLElement, e) {
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
        assert(message !== undefined);
        starred_messages_ui.toggle_starred_and_update_server(message);
    });

    $("#main_div").on("click", ".message_reaction", function (this: HTMLElement, e) {
        e.stopPropagation();

        if (page_params.is_spectator) {
            spectators.login_to_access();
            return;
        }

        emoji_picker.hide_emoji_popover();
        const local_id = $(this).attr("data-reaction-id")!;
        const message_id = rows.get_message_id(this);
        reactions.process_reaction_click(message_id, local_id);
    });

    $("body").on("click", ".reveal_hidden_message", (e) => {
        assert(message_lists.current !== undefined);
        const message_id = rows.id($(e.currentTarget).closest(".message_row"));
        message_lists.current.view.reveal_hidden_message(message_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("#main_div").on("click", "a.stream", function (this: HTMLAnchorElement, e) {
        e.preventDefault();
        // Note that we may have an href here, but we trust the stream id more,
        // so we re-encode the hash.
        const stream_id = Number.parseInt($(this).attr("data-stream-id")!, 10);
        if (stream_id) {
            browser_history.go_to_location(hash_util.channel_url_by_user_setting(stream_id));
            return;
        }
        window.location.href = this.href;
    });

    $("body").on("click", "#scroll-to-bottom-button-clickable-area", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Since it take a few milliseconds for this button complete disappear transition,
        // it is possible for user to click it before it hides when switching narrows.
        if (narrow_state.is_message_feed_visible()) {
            navigate.to_end();
        }
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
        assert(message?.type === "stream");
        void stream_popover.build_move_topic_to_stream_popover(
            message.stream_id,
            message.topic,
            false,
            message,
        );
        e.stopPropagation();
    });
    $("body").on("click", ".on_hover_topic_edit", function (e) {
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
        void message_edit.save_message_row_edit($row);
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
        $(`#edit_form_${CSS.escape(`${row_id}`)} .file_input`).trigger("click");
    });
    $("body").on(
        "focus",
        ".message_edit_form textarea.message_edit_content",
        function (this: HTMLTextAreaElement, _event) {
            compose_state.set_last_focused_compose_type_input(this);
        },
    );

    $("body").on("click", ".message_edit_form .markdown_preview", function (this: HTMLElement, e) {
        e.preventDefault();
        message_edit.show_preview_area($(this));
    });

    $("body").on(
        "click",
        ".message_edit_form .undo_markdown_preview",
        function (this: HTMLElement, e) {
            e.preventDefault();
            message_edit.clear_preview_area($(this));
        },
    );

    $("body").on("input", ".message_edit_form textarea", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");

        if ($row.hasClass("preview_mode")) {
            message_edit.render_preview_area($row);
        }
    });

    // RESOLVED TOPICS
    $("body").on("click", ".message_header .on_hover_topic_resolve", (e) => {
        e.stopPropagation();
        const $recipient_row = $(e.target).closest(".recipient_row");
        const message_id = rows.id_for_recipient_row($recipient_row);
        const topic_name = $(e.target).closest(".message_header").attr("data-topic-name")!;
        message_edit.toggle_resolve_topic(message_id, topic_name, false, $recipient_row);
    });

    // RECIPIENT BARS

    function get_row_id_for_narrowing(narrow_link_elem: HTMLElement): number {
        const $group = rows.get_closest_group(narrow_link_elem);
        const msg_id = rows.id_for_recipient_row($group);

        assert(message_lists.current !== undefined);
        const nearest = message_lists.current.get(msg_id)!;
        const selected = message_lists.current.selected_message();
        if (selected !== undefined && util.same_recipient(nearest, selected)) {
            return selected.id;
        }
        return nearest.id;
    }

    $("#message_feed_container").on(
        "click",
        ".narrows_by_recipient",
        function (this: HTMLElement, e) {
            if (e.metaKey || e.ctrlKey || e.shiftKey) {
                return;
            }
            e.preventDefault();
            const row_id = get_row_id_for_narrowing(this);
            // TODO: Navigate user according to `web_channel_default_view` setting.
            // Also, update the tooltip hotkey in recipient bar.
            message_view.narrow_by_recipient(row_id, {trigger: "message header"});
        },
    );

    $("#message_feed_container").on("click", ".narrows_by_topic", function (this: HTMLElement, e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        message_view.narrow_by_topic(row_id, {trigger: "message header"});
    });

    // SIDEBARS
    $("body").on("click", "#compose-new-direct-message", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_actions.start({
            message_type: "private",
            trigger: "new direct message",
            keep_composebox_empty: true,
        });
    });

    $(".buddy-list-section").on("click", ".selectable_sidebar_block", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) {
            return;
        }
        if ($(e.target).parents(".user-profile-picture").length === 1) {
            return;
        }

        const $li = $(e.target).parents("li");

        activity_ui.narrow_for_user({$li});

        e.preventDefault();
        e.stopPropagation();
        sidebar_ui.hide_userlist_sidebar();
    });

    // Doesn't show tooltip on touch devices.
    function do_render_buddy_list_tooltip(
        $elem: JQuery,
        title_data: buddy_data.TitleData,
        get_target_node?: (tippy_instance: tippy.Instance) => HTMLElement,
        check_reference_removed?: (
            mutation: MutationRecord,
            tippy_instance: tippy.Instance,
        ) => boolean,
        subtree = false,
        parent_element_to_append: HTMLElement | null = null,
        is_custom_observer_needed = true,
    ): void {
        let placement: tippy.Placement = "left";
        let observer: MutationObserver;
        if (ui_util.matches_viewport_state("lt_md_min")) {
            // On small devices display tooltips based on available space.
            // This will default to "bottom" placement for this tooltip.
            placement = "auto";
        }
        tippy.default(util.the($elem), {
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
            onCreate(instance) {
                const $popover = $(instance.popper);
                $popover.addClass("buddy-list-tooltip-root");
            },
            onShow(instance) {
                if (!is_custom_observer_needed) {
                    return;
                }
                assert(get_target_node !== undefined);
                assert(check_reference_removed !== undefined);
                // We cannot use MutationObserver directly on the reference element because
                // it will be removed and we need to attach it on an element which will remain in the DOM.
                const target_node = get_target_node(instance);
                // We only need to know if any of the `li` elements were removed.
                const config = {attributes: false, childList: true, subtree};
                const callback: MutationCallback = function (mutationsList) {
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
            appendTo: () => parent_element_to_append ?? document.body,
        });
    }

    // BUDDY LIST TOOLTIPS (not displayed on touch devices)
    $(".buddy-list-section").on(
        "mouseenter",
        ".user_sidebar_entry",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            const $elem = $(this);

            const user_id_string = $elem.attr("data-user-id")!;
            const title_data = buddy_data.get_title_data(user_id_string, false);

            // `target_node` is the `ul` element since it stays in DOM even after updates.
            function get_target_node(): HTMLElement {
                return util.the($(e.target).parents(".buddy-list-section"));
            }

            function check_reference_removed(
                mutation: MutationRecord,
                instance: tippy.Instance,
            ): boolean {
                return Array.prototype.includes.call(mutation.removedNodes, instance.reference);
            }

            do_render_buddy_list_tooltip(
                $elem,
                title_data,
                get_target_node,
                check_reference_removed,
            );

            /*
            The following implements a little tooltip giving the name for status emoji
            when hovering them in the right sidebar. This requires special logic, to avoid
            conflicting with the main tooltip or showing duplicate tooltips.
            */
            $(".user_sidebar_entry .status-emoji-name").off("mouseenter").off("mouseleave");
            $(".user_sidebar_entry .status-emoji-name").on("mouseenter", () => {
                const element: tippy.ReferenceElement = util.the($elem);
                const instance = element._tippy;
                // We make sure instance is of buddy list since we don't want to
                // close any other tippy instances.
                if (
                    instance?.state.isVisible &&
                    instance.reference.classList.contains("user_sidebar_entry") &&
                    instance.popper.classList.contains("buddy-list-tooltip-root")
                ) {
                    instance.destroy();
                }
            });
            $(".user_sidebar_entry .status-emoji-name").on("mouseleave", () => {
                do_render_buddy_list_tooltip(
                    $elem,
                    title_data,
                    get_target_node,
                    check_reference_removed,
                );
            });
        },
    );

    // DIRECT MESSAGE LIST TOOLTIPS (not displayed on touch devices)
    $("body").on("mouseenter", ".dm-user-status", function (this: HTMLElement, e) {
        e.stopPropagation();
        const $elem = $(this);
        const user_ids_string = $elem.attr("data-user-ids-string")!;
        // This converts from 'true' in the DOM to true.
        const is_group = z.boolean().parse(JSON.parse($elem.attr("data-is-group")!));

        const title_data = buddy_data.get_title_data(user_ids_string, is_group);

        // Since anything inside `#left_sidebar_scroll_container` can be replaced, it is our target node here.
        function get_target_node(): HTMLElement {
            return document.querySelector("#left_sidebar_scroll_container")!;
        }

        // Whole list is just replaced, so we need to check for that.
        function check_reference_removed(
            mutation: MutationRecord,
            instance: tippy.Instance,
        ): boolean {
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
            const element: tippy.ReferenceElement = util.the($elem);
            const instance = element._tippy;
            if (instance?.state.isVisible) {
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
    $("body").on(
        "mouseenter",
        ".recent_topic_stream .pm_status_icon",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            const $elem = $(this);
            const user_ids_string = $elem.attr("data-user-ids-string");
            // Don't show tooltip for group direct messages.
            if (!user_ids_string || user_ids_string.split(",").length !== 1) {
                return;
            }
            const title_data = recent_view_ui.get_pm_tooltip_data(user_ids_string);
            do_render_buddy_list_tooltip(
                $elem,
                title_data,
                undefined,
                undefined,
                false,
                undefined,
                false,
            );
        },
    );

    // MISC

    {
        const sel = [
            "#stream_filters",
            "#left-sidebar-navigation-list",
            "#buddy-list-users-matching-view",
        ].join(", ");

        $(sel).on("click", "a", function (this: HTMLElement) {
            this.blur();
        });
    }

    $("body").on("click", ".logout_button", () => {
        $("#logout_form").trigger("submit");
    });

    $("#settings_page").on("click", ".collapse-settings-button", () => {
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
        const target = $(this).attr("data-overlay-trigger")!;
        browser_history.go_to_location(target);
    });

    $("body").on("click", ".formatting-control-scroller-button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const $target = $(e.currentTarget);
        const $button_container = $target.closest(".compose-scrolling-buttons-container");
        const $button_bar = $button_container.find(".compose-scrollable-buttons");

        const button_container_width = Number(
            $button_container.attr("data-button-container-width"),
        );
        const button_bar_max_left_scroll = Number(
            $button_container.attr("data-button-bar-max-left-scroll"),
        );
        const button_bar_scroll_left = Number($button_bar.scrollLeft());

        // Buttons do not scale, so as to provide a generous click
        // area while not overwhelming the visibility of buttons on
        // narrower viewports at larger font sizes
        const scroller_button_width_px = 48;
        // We scroll 80% of the viewable area on each click...
        const button_bar_scroll_percentage = 80 / 100;
        // ...less the width of the two scroller buttons.
        const button_adjusted_scroll_shift =
            button_bar_scroll_percentage * (button_container_width - 2 * scroller_button_width_px);
        let new_scroll_position = 0;

        assert(typeof button_bar_scroll_left === "number");

        if ($target.hasClass("formatting-scroller-forward")) {
            new_scroll_position = button_bar_scroll_left + button_adjusted_scroll_shift;
            // If we're less than the width of the scroller button from
            // the end, just scroll the rest of the way forward
            if (button_bar_max_left_scroll <= new_scroll_position - scroller_button_width_px) {
                new_scroll_position = button_bar_max_left_scroll;
            }
        } else {
            new_scroll_position = button_bar_scroll_left - button_adjusted_scroll_shift;
            // If we're less than the width of the scroller button from
            // the start, just scroll the rest of the way back
            if (new_scroll_position <= scroller_button_width_px) {
                new_scroll_position = 0;
            }
        }

        $button_bar.scrollLeft(new_scroll_position);
    });

    function handle_compose_click(e: JQuery.ClickEvent): void {
        const $target = $(e.target);
        // Emoji clicks should be handled by their own click handler in emoji_picker.js
        if ($target.is(".emoji_map, img.emoji, .drag, .compose_gif_icon")) {
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

    $("body").on(
        "focus",
        "textarea#compose-textarea",
        function (this: HTMLTextAreaElement, _event: JQuery.Event) {
            compose_state.set_last_focused_compose_type_input(this);
        },
    );

    // LEFT SIDEBAR

    $("body").on("click", ".filter-topics .input-button", topic_list.clear_topic_search);

    $(".streams_filter_icon").on("click", (e) => {
        e.stopPropagation();
        stream_list.toggle_filter_displayed(e);
    });

    $("body").on("click", "#direct-messages-section-header.zoom-out", (e) => {
        if ($(e.target).closest("#show-all-direct-messages").length === 1) {
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
    });

    /* The DIRECT MESSAGES label's click behavior is complicated;
     * only when zoomed in does it have a navigation effect, so we need
     * this click handler rather than just a link. */
    $("body").on("click", "#direct-messages-section-header.zoom-in", (e) => {
        e.preventDefault();
        e.stopPropagation();

        window.location.hash = "narrow/is/dm";
    });

    $("body").on("click", ".direct-messages-search-section", (e) => {
        // We don't want clicking on the filter to trigger the DM
        // narrow defined on click for
        // `#direct-messages-section-header.zoom-in`.
        e.stopPropagation();
    });

    // disable the draggability for left-sidebar components
    $("#stream_filters, #left-sidebar-navigation-list").on("dragstart", (e) => {
        e.target.blur();
        return false;
    });

    // Chrome focuses an element when dragging it which can be confusing when
    // users involuntarily drag something and we show them the focus outline.
    $("body").on("dragstart", "a", function (this: HTMLElement) {
        this.blur();
    });

    // Don't focus links on middle click.
    $("body").on("mouseup", "a", function (this: HTMLElement, e) {
        if (e.button === 1) {
            // middle click
            this.blur();
        }
    });

    // Don't focus links on context menu.
    $("body").on("contextmenu", "a", function (this: HTMLElement) {
        this.blur();
    });

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

        if (compose_state.composing() && $(e.target).parents("#compose").length === 0) {
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
                !window.getSelection()?.toString() &&
                // Clicking any input or text area should not close
                // the compose box; this means using the sidebar
                // filters or search widgets won't unnecessarily close
                // compose.
                $(e.target).closest("input").length === 0 &&
                $(e.target).closest(".todo-widget label.checkbox").length === 0 &&
                $(e.target).closest("textarea").length === 0 &&
                $(e.target).closest("select").length === 0 &&
                // Clicks inside an overlay, popover, custom
                // modal, or backdrop of one of the above
                // should not have any effect on the compose
                // state.
                $(e.target).closest(".overlay").length === 0 &&
                $(e.target).closest(".micromodal").length === 0 &&
                $(e.target).closest("[data-tippy-root]").length === 0 &&
                $(e.target).closest(".typeahead").length === 0 &&
                $(e.target).closest(".flatpickr-calendar").length === 0 &&
                $(e.target).closest("body").length > 0
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
}
