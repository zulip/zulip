import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";
import WinChan from "winchan";

// You won't find every click handler here, but it's a good place to start!

import render_buddy_list_tooltip_content from "../templates/buddy_list_tooltip_content.hbs";

import * as activity from "./activity";
import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as buddy_data from "./buddy_data";
import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_error from "./compose_error";
import * as compose_state from "./compose_state";
import {media_breakpoints_num} from "./css_variables";
import * as emoji_picker from "./emoji_picker";
import * as hash_util from "./hash_util";
import * as hotspots from "./hotspots";
import * as message_edit from "./message_edit";
import * as message_flags from "./message_flags";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as muted_topics_ui from "./muted_topics_ui";
import * as narrow from "./narrow";
import * as notifications from "./notifications";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as reactions from "./reactions";
import * as recent_topics_ui from "./recent_topics_ui";
import * as rows from "./rows";
import * as server_events from "./server_events";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_toggle from "./settings_toggle";
import * as stream_list from "./stream_list";
import * as stream_popover from "./stream_popover";
import * as topic_list from "./topic_list";
import * as ui_util from "./ui_util";
import * as unread_ops from "./unread_ops";
import * as user_profile from "./user_profile";
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

    function is_clickable_message_element(target) {
        // This function defines all the elements within a message
        // body that have UI behavior other than starting a reply.

        // Links should be handled by the browser.
        if (target.closest("a").length > 0) {
            return true;
        }

        // Forms for message editing contain input elements
        if (target.is("textarea") || target.is("input")) {
            return true;
        }

        // Widget for adjusting the height of a message.
        if (target.is("div.message_length_controller")) {
            return true;
        }

        // Inline image and twitter previews.
        if (target.is("img.message_inline_image") || target.is("img.twitter-avatar")) {
            return true;
        }

        // UI elements for triggering message editing or viewing edit history.
        if (target.is("i.edit_content_button") || target.is(".message_edit_notice")) {
            return true;
        }

        // For spoilers, allow clicking either the header or elements within it
        if (target.is(".spoiler-header") || target.parents(".spoiler-header").length > 0) {
            return true;
        }

        // Ideally, this should be done via ClipboardJS, but it doesn't support
        // feature of stopPropagation once clicked.
        // See https://github.com/zenorocha/clipboard.js/pull/475
        if (target.is(".copy_codeblock") || target.parents(".copy_codeblock").length > 0) {
            return true;
        }

        // Don't select message on clicking message control buttons.
        if (target.parents(".message_controls").length > 0) {
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

        const row = $(this).closest(".message_row");
        const id = rows.id(row);

        if (message_edit.is_editing(id)) {
            // Clicks on a message being edited shouldn't trigger a reply.
            return;
        }

        message_lists.current.select_id(id);

        if (page_params.is_spectator) {
            return;
        }
        compose_actions.respond_to_message({trigger: "message click"});
        e.stopPropagation();
        popovers.hide_all();
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
        popovers.hide_all();

        const message_id = rows.id($(this).closest(".message_row"));
        const message = message_store.get(message_id);
        message_flags.toggle_starred_and_update_server(message);
    });

    $("#main_div").on("click", ".message_reaction", function (e) {
        e.stopPropagation();
        emoji_picker.hide_emoji_popover();
        const local_id = $(this).attr("data-reaction-id");
        const message_id = rows.get_message_id(this);
        reactions.process_reaction_click(message_id, local_id);
        $(".tooltip").remove();
    });

    $("body").on("click", ".reveal_hidden_message", (e) => {
        // Hide actions popover to keep its options
        // in sync with revealed/hidden state of
        // muted user's message.
        popovers.hide_actions_popover();

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
            browser_history.go_to_location(hash_util.by_stream_uri(stream_id));
            return;
        }
        window.location.href = $(this).attr("href");
    });

    // MESSAGE EDITING

    $("body").on("click", ".edit_content_button", function (e) {
        const row = message_lists.current.get_row(rows.id($(this).closest(".message_row")));
        message_lists.current.select_id(rows.id(row));
        message_edit.start(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".always_visible_topic_edit,.on_hover_topic_edit", function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        message_edit.start_inline_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_save", function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        message_edit.save_inline_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".topic_edit_cancel", function (e) {
        const recipient_row = $(this).closest(".recipient_row");
        message_edit.end_inline_topic_edit(recipient_row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_save", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.save_message_row_edit(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_cancel", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.end_message_row_edit(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", ".message_edit_close", function (e) {
        const row = $(this).closest(".message_row");
        message_edit.end_message_row_edit(row);
        e.stopPropagation();
        popovers.hide_all();
    });
    $("body").on("click", "a", function () {
        if (document.activeElement === this) {
            ui_util.blur_active_element();
        }
    });
    $(".message_edit_form .send-status-close").on("click", function () {
        const row_id = rows.id($(this).closest(".message_row"));
        const send_status = $(`#message-edit-send-status-${CSS.escape(row_id)}`);
        $(send_status).stop(true).fadeOut(200);
    });
    $("body").on("click", ".message_edit_form .compose_upload_file", function (e) {
        e.preventDefault();

        const row_id = rows.id($(this).closest(".message_row"));
        $(`#edit_form_${CSS.escape(row_id)} .file_input`).trigger("click");
    });

    $("body").on("click", ".message_edit_form .markdown_preview", (e) => {
        e.preventDefault();
        const row = rows.get_closest_row(e.target);
        const $msg_edit_content = row.find(".message_edit_content");
        const content = $msg_edit_content.val();
        $msg_edit_content.hide();
        row.find(".markdown_preview").hide();
        row.find(".undo_markdown_preview").show();
        row.find(".preview_message_area").show();

        compose.render_and_show_preview(
            row.find(".markdown_preview_spinner"),
            row.find(".preview_content"),
            content,
        );
    });

    $("body").on("click", ".message_edit_form .undo_markdown_preview", (e) => {
        e.preventDefault();
        const row = rows.get_closest_row(e.target);
        row.find(".message_edit_content").show();
        row.find(".undo_markdown_preview").hide();
        row.find(".preview_message_area").hide();
        row.find(".preview_content").empty();
        row.find(".markdown_preview").show();
    });

    // RESOLVED TOPICS
    $("body").on("click", ".message_header .on_hover_topic_resolve", (e) => {
        e.stopPropagation();
        const recipient_row = $(e.target).closest(".recipient_row");
        const message_id = rows.id_for_recipient_row(recipient_row);
        const topic_name = $(e.target).attr("data-topic-name");
        message_edit.toggle_resolve_topic(message_id, topic_name);
    });

    $("body").on("click", ".message_header .on_hover_topic_unresolve", (e) => {
        e.stopPropagation();
        const recipient_row = $(e.target).closest(".recipient_row");
        const message_id = rows.id_for_recipient_row(recipient_row);
        const topic_name = $(e.target).attr("data-topic-name");
        message_edit.toggle_resolve_topic(message_id, topic_name);
    });

    // TOPIC MUTING
    function mute_or_unmute_topic($elt, mute_topic) {
        const stream_id = Number.parseInt($elt.attr("data-stream-id"), 10);
        const topic = $elt.attr("data-topic-name");
        if (mute_topic) {
            muted_topics_ui.mute_topic(stream_id, topic);
        } else {
            muted_topics_ui.unmute_topic(stream_id, topic);
        }
    }

    $("body").on("click", ".message_header .on_hover_topic_mute", (e) => {
        e.stopPropagation();
        mute_or_unmute_topic($(e.target), true);
    });

    $("body").on("click", ".message_header .on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        mute_or_unmute_topic($(e.target), false);
    });

    // RECENT TOPICS

    $("#recent_topics_table").on("click", ".participant_profile", function (e) {
        const participant_user_id = Number.parseInt($(this).attr("data-user-id"), 10);
        e.stopPropagation();
        const user = people.get_by_user_id(participant_user_id);
        popovers.show_user_info_popover(this, user);
    });

    $("body").on("keydown", ".on_hover_topic_mute", ui_util.convert_enter_to_click);

    $("body").on("click", "#recent_topics_table .on_hover_topic_unmute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        recent_topics_ui.focus_clicked_element(topic_row_index, recent_topics_ui.COLUMNS.mute);
        mute_or_unmute_topic($elt, false);
    });

    $("body").on("keydown", ".on_hover_topic_unmute", ui_util.convert_enter_to_click);

    $("body").on("click", "#recent_topics_table .on_hover_topic_mute", (e) => {
        e.stopPropagation();
        const $elt = $(e.target);
        const topic_row_index = $elt.closest("tr").index();
        recent_topics_ui.focus_clicked_element(topic_row_index, recent_topics_ui.COLUMNS.mute);
        mute_or_unmute_topic($elt, true);
    });

    $("body").on("click", "#recent_topics_search", (e) => {
        e.stopPropagation();
        recent_topics_ui.change_focused_element($(e.target), "click");
    });

    $("body").on("click", "#recent_topics_table .on_hover_topic_read", (e) => {
        e.stopPropagation();
        const topic_row_index = $(e.target).closest("tr").index();
        recent_topics_ui.focus_clicked_element(topic_row_index, recent_topics_ui.COLUMNS.read);
        const stream_id = Number.parseInt($(e.currentTarget).attr("data-stream-id"), 10);
        const topic = $(e.currentTarget).attr("data-topic-name");
        unread_ops.mark_topic_as_read(stream_id, topic);
    });

    $("body").on("keydown", ".on_hover_topic_read", ui_util.convert_enter_to_click);

    $("body").on("click", ".btn-recent-filters", (e) => {
        e.stopPropagation();
        recent_topics_ui.change_focused_element($(e.target), "click");
        recent_topics_ui.set_filter(e.currentTarget.dataset.filter);
        recent_topics_ui.update_filters_view();
        recent_topics_ui.revive_current_focus();
    });

    $("body").on("click", "td.recent_topic_stream", (e) => {
        e.stopPropagation();
        const topic_row_index = $(e.target).closest("tr").index();
        recent_topics_ui.focus_clicked_element(topic_row_index, recent_topics_ui.COLUMNS.stream);
        window.location.href = $(e.currentTarget).find("a").attr("href");
    });

    $("body").on("click", "td.recent_topic_name", (e) => {
        e.stopPropagation();
        // The element's parent may re-render while it is being passed to
        // other functions, so, we get topic_key first.
        const topic_row = $(e.target).closest("tr");
        const topic_key = topic_row.attr("id").slice("recent_topics:".length - 1);
        const topic_row_index = topic_row.index();
        recent_topics_ui.focus_clicked_element(
            topic_row_index,
            recent_topics_ui.COLUMNS.topic,
            topic_key,
        );
        window.location.href = $(e.currentTarget).find("a").attr("href");
    });

    // Search for all table rows (this combines stream & topic names)
    $("body").on(
        "keyup",
        "#recent_topics_search",
        _.debounce(() => {
            recent_topics_ui.update_filters_view();
            // Wait for user to go idle before initiating search.
        }, 300),
    );

    $("body").on("click", "#recent_topics_search_clear", (e) => {
        e.stopPropagation();
        $("#recent_topics_search").val("");
        recent_topics_ui.update_filters_view();
    });

    // RECIPIENT BARS

    function get_row_id_for_narrowing(narrow_link_elem) {
        const group = rows.get_closest_group(narrow_link_elem);
        const msg_id = rows.id_for_recipient_row(group);

        const nearest = message_lists.current.get(msg_id);
        const selected = message_lists.current.selected_message();
        if (util.same_recipient(nearest, selected)) {
            return selected.id;
        }
        return nearest.id;
    }

    $("#message_feed_container").on("click", ".narrows_by_recipient", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_recipient(row_id, {trigger: "message header"});
    });

    $("#message_feed_container").on("click", ".narrows_by_topic", function (e) {
        if (e.metaKey || e.ctrlKey) {
            return;
        }
        e.preventDefault();
        const row_id = get_row_id_for_narrowing(this);
        narrow.by_topic(row_id, {trigger: "message header"});
    });

    // SIDEBARS

    $("#userlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-right").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            popovers.show_userlist_sidebar();
        }
    });

    $("#streamlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-left").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            stream_popover.show_streamlist_sidebar();
        }
    });

    $("#user_presences")
        .expectOne()
        .on("click", ".selectable_sidebar_block", (e) => {
            const li = $(e.target).parents("li");

            activity.narrow_for_user({li});

            e.preventDefault();
            e.stopPropagation();
            popovers.hide_all();
            $(".tooltip").remove();
        });

    function do_render_buddy_list_tooltip(elem, title_data) {
        let placement = "left";
        let observer;
        if (window.innerWidth < media_breakpoints_num.md) {
            // On small devices display tooltips based on available space.
            // This will default to "bottom" placement for this tooltip.
            placement = "auto";
        }
        tippy(elem[0], {
            // Quickly display and hide right sidebar tooltips
            // so that they don't stick and overlap with
            // each other.
            delay: 0,
            content: render_buddy_list_tooltip_content(title_data),
            arrow: true,
            placement,
            allowHTML: true,
            showOnCreate: true,
            onHidden: (instance) => {
                instance.destroy();
                observer.disconnect();
            },
            onShow: (instance) => {
                // For both buddy list and top left corner pm list, `target_node`
                // is their parent `ul` element. We cannot use MutationObserver
                // directly on the reference element because it will be removed
                // and we need to attach it on an element which will remain in the
                // DOM which is their parent `ul`.
                const target_node = $(instance.reference).parents("ul").get(0);
                // We only need to know if any of the `li` elements were removed.
                const config = {attributes: false, childList: true, subtree: false};
                const callback = function (mutationsList) {
                    for (const mutation of mutationsList) {
                        // Hide instance if reference is in the removed node list.
                        if (
                            Array.prototype.includes.call(
                                mutation.removedNodes,
                                instance.reference.parentElement,
                            )
                        ) {
                            instance.hide();
                        }
                    }
                };
                observer = new MutationObserver(callback);
                observer.observe(target_node, config);
            },
            appendTo: () => document.body,
        });
    }

    // BUDDY LIST TOOLTIPS
    $("#user_presences").on("mouseenter", ".selectable_sidebar_block", (e) => {
        e.stopPropagation();
        const elem = $(e.currentTarget).closest(".user_sidebar_entry").find(".user-presence-link");
        const user_id_string = elem.attr("data-user-id");
        const title_data = buddy_data.get_title_data(user_id_string, false);
        do_render_buddy_list_tooltip(elem.parent(), title_data);
    });

    // PM LIST TOOLTIPS
    $("body").on("mouseenter", "#pm_user_status", (e) => {
        e.stopPropagation();
        const elem = $(e.currentTarget);
        const user_ids_string = elem.attr("data-user-ids-string");
        // This converts from 'true' in the DOM to true.
        const is_group = JSON.parse(elem.attr("data-is-group"));

        const title_data = buddy_data.get_title_data(user_ids_string, is_group);
        do_render_buddy_list_tooltip(elem, title_data);
    });

    // MISC

    {
        const sel = ["#stream_filters", "#global_filters", "#user_presences"].join(", ");

        $(sel).on("click", "a", function () {
            this.blur();
        });
    }

    popovers.register_click_handlers();
    user_profile.register_click_handlers();
    emoji_picker.register_click_handlers();
    stream_popover.register_click_handlers();
    notifications.register_click_handlers();

    $("body").on("click", ".logout_button", () => {
        $("#logout_form").trigger("submit");
    });

    $(".restart_get_events_button").on("click", () => {
        server_events.restart_get_events({dont_block: true});
    });

    $("#settings_page").on("click", ".collapse-settings-btn", () => {
        settings_toggle.toggle_org_setting_collapse();
    });

    $(".organization-box").on("show.bs.modal", () => {
        popovers.hide_all();
    });

    // COMPOSE

    $("body").on("click", "#compose-send-status .compose-send-status-close", () => {
        compose_error.hide();
    });

    $("body").on("click", ".empty_feed_compose_stream", (e) => {
        compose_actions.start("stream", {trigger: "empty feed message"});
        e.preventDefault();
    });
    $("body").on("click", ".empty_feed_compose_private", (e) => {
        compose_actions.start("private", {trigger: "empty feed message"});
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

        // The mobile compose button has its own popover when clicked, so it already.
        // hides other popovers.
        if ($target.is(".compose_mobile_button, .compose_mobile_button *")) {
            return;
        }

        if ($(".enter_sends").has(e.target).length) {
            e.preventDefault();
            return;
        }

        // Don't let clicks in the compose area count as
        // "unfocusing" our compose -- in other words, e.g.
        // clicking "Press Enter to send" should not
        // trigger the composebox-closing code in MAIN CLICK HANDLER.
        // But do allow our formatting link.
        if (!$target.is("a")) {
            e.stopPropagation();
        }
        // Still hide the popovers, however
        popovers.hide_all();
    }

    $("body").on("click", "#compose-content", handle_compose_click);

    $("body").on("click", "#compose_close", () => {
        compose_actions.cancel();
    });

    // LEFT SIDEBAR

    $("body").on("click", "#clear_search_topic_button", topic_list.clear_topic_search);

    $(".streams_filter_icon").on("click", (e) => {
        e.stopPropagation();
        stream_list.toggle_filter_displayed(e);
    });

    // WEBATHENA

    $("body").on("click", ".webathena_login", (e) => {
        $("#zephyr-mirror-error").removeClass("show");
        const principal = ["zephyr", "zephyr"];
        WinChan.open(
            {
                url: "https://webathena.mit.edu/#!request_ticket_v1",
                relay_url: "https://webathena.mit.edu/relay.html",
                params: {
                    realm: "ATHENA.MIT.EDU",
                    principal,
                },
            },
            (err, r) => {
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
                    success() {
                        $("#zephyr-mirror-error").removeClass("show");
                    },
                    error() {
                        $("#zephyr-mirror-error").addClass("show");
                    },
                });
            },
        );
        $("#settings-dropdown").dropdown("toggle");
        e.preventDefault();
        e.stopPropagation();
    });
    // End Webathena code

    // disable the draggability for left-sidebar components
    $("#stream_filters, #global_filters").on("dragstart", (e) => {
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

    // HOTSPOTS

    // open
    $("body").on("click", ".hotspot-icon", function (e) {
        // hide icon
        hotspots.close_hotspot_icon(this);

        // show popover
        const hotspot_name = $(e.target)
            .closest(".hotspot-icon")
            .attr("id")
            .replace("hotspot_", "")
            .replace("_icon", "");
        const overlay_name = "hotspot_" + hotspot_name + "_overlay";

        overlays.open_overlay({
            name: overlay_name,
            overlay: $(`#${CSS.escape(overlay_name)}`),
            on_close: function () {
                // close popover
                $(this).css({display: "block"});
                $(this).animate(
                    {opacity: 1},
                    {
                        duration: 300,
                    },
                );
            }.bind(this),
        });

        e.preventDefault();
        e.stopPropagation();
    });

    // confirm
    $("body").on("click", ".hotspot.overlay .hotspot-confirm", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const overlay_name = $(this).closest(".hotspot.overlay").attr("id");

        const hotspot_name = overlay_name.replace("hotspot_", "").replace("_overlay", "");

        // Comment below to disable marking hotspots as read in production
        hotspots.post_hotspot_as_read(hotspot_name);

        overlays.close_overlay(overlay_name);
        $(`#hotspot_${CSS.escape(hotspot_name)}_icon`).remove();
    });

    // stop propagation
    $("body").on("click", ".hotspot.overlay .hotspot-popover", (e) => {
        e.stopPropagation();
    });

    $("body").on("hidden.bs.modal", () => {
        // Enable mouse events for the background as the modal closes.
        overlays.enable_background_mouse_events();

        // TODO: Remove this once Bootstrap is upgraded.
        // See: https://github.com/zulip/zulip/pull/18720
        $(".modal.in").removeClass("in");
    });

    // MAIN CLICK HANDLER

    $(document).on("click", (e) => {
        if (e.button !== 0 || $(e.target).is(".drag")) {
            // Firefox emits right click events on the document, but not on
            // the child nodes, so the #compose stopPropagation doesn't get a
            // chance to capture right clicks.
            return;
        }

        // Dismiss popovers if the user has clicked outside them
        if (
            $(
                '.popover-inner, #user-profile-modal, .emoji-info-popover, .app-main [class^="column-"].expanded',
            ).has(e.target).length === 0
        ) {
            // Since tippy instance can handle outside clicks on their own,
            // we don't need to trigger them from here.
            // This fixes the bug of `hideAll` being called
            // after a tippy popover has been triggered which hides
            // the popover without being displayed.
            const not_hide_tippy_instances = true;
            popovers.hide_all(not_hide_tippy_instances);
        }

        if (compose_state.composing()) {
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
                $("#compose-textarea").trigger("focus");
                return;
            } else if (
                !window.getSelection().toString() &&
                // Clicking any input or text area should not close
                // the compose box; this means using the sidebar
                // filters or search widgets won't unnecessarily close
                // compose.
                !$(e.target).closest("input").length &&
                !$(e.target).closest("textarea").length &&
                !$(e.target).closest("select").length &&
                // Clicks inside an overlay, popover, custom
                // modal, or backdrop of one of the above
                // should not have any effect on the compose
                // state.
                !$(e.target).closest(".overlay").length &&
                !$(e.target).closest(".popover").length &&
                !$(e.target).closest(".modal").length &&
                !$(e.target).closest(".micromodal").length &&
                !$(e.target).closest("[data-tippy-root]").length &&
                !$(e.target).closest(".modal-backdrop").length &&
                !$(e.target).closest(".enter_sends").length &&
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
    $("a.dropdown-toggle, .dropdown-menu a").on("touchstart", (e) => {
        e.stopPropagation();
    });

    $(".settings-header.mobile .fa-chevron-left").on("click", () => {
        settings_panel_menu.mobile_deactivate_section();
    });
}
