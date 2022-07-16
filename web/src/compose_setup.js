import $ from "jquery";

import render_add_poll_modal from "../templates/add_poll_modal.hbs";

import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_call from "./compose_call";
import * as compose_call_ui from "./compose_call_ui";
import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as dialog_widget from "./dialog_widget";
import * as flatpickr from "./flatpickr";
import {$t_html} from "./i18n";
import * as message_edit from "./message_edit";
import * as narrow from "./narrow";
import {page_params} from "./page_params";
import * as poll_modal from "./poll_modal";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as rows from "./rows";
import * as scheduled_messages from "./scheduled_messages";
import * as scheduled_messages_popover from "./scheduled_messages_popover";
import * as stream_data from "./stream_data";
import * as stream_settings_components from "./stream_settings_components";
import * as sub_store from "./sub_store";
import * as subscriber_api from "./subscriber_api";
import {get_timestamp_for_flatpickr} from "./timerender";
import * as ui_report from "./ui_report";
import * as upload from "./upload";
import * as user_topics from "./user_topics";

export function abort_xhr() {
    $("#compose-send-button").prop("disabled", false);
    upload.compose_upload_object.cancelAll();
}

function setup_compose_actions_hooks() {
    compose_actions.register_compose_box_clear_hook(compose.clear_invites);
    compose_actions.register_compose_box_clear_hook(compose.clear_private_stream_alert);
    compose_actions.register_compose_box_clear_hook(compose.clear_preview_area);

    compose_actions.register_compose_cancel_hook(abort_xhr);
    compose_actions.register_compose_cancel_hook(compose_call.abort_video_callbacks);
}

export function initialize() {
    // Register hooks for compose_actions.
    setup_compose_actions_hooks();

    $("#below-compose-content .video_link").toggle(compose_call.compute_show_video_chat_button());
    $("#below-compose-content .audio_link").toggle(compose_call.compute_show_audio_chat_button());

    $("#compose-textarea").on("keydown", (event) => {
        compose_ui.handle_keydown(event, $("#compose-textarea").expectOne());
    });
    $("#compose-textarea").on("keyup", (event) => {
        compose_ui.handle_keyup(event, $("#compose-textarea").expectOne());
    });

    $("#compose-textarea").on("input propertychange", () => {
        compose_validate.warn_if_topic_resolved(false);
        const compose_text_length = compose_validate.check_overflow_text();
        if (compose_text_length !== 0 && $("#compose-textarea").hasClass("invalid")) {
            $("#compose-textarea").toggleClass("invalid", false);
        }
        // Change compose close button tooltip as per condition.
        // We save compose text in draft only if its length is > 2.
        if (compose_text_length > 2) {
            $("#compose_close").attr(
                "data-tooltip-template-id",
                "compose_close_and_save_tooltip_template",
            );
        } else {
            $("#compose_close").attr("data-tooltip-template-id", "compose_close_tooltip_template");
        }

        // The poll widget requires an empty compose box.
        if (compose_text_length > 0) {
            $(".add-poll").parent().addClass("disabled");
        } else {
            $(".add-poll").parent().removeClass("disabled");
        }
    });

    $("#compose form").on("submit", (e) => {
        e.preventDefault();
        compose.finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    // Updates compose max-height and scroll to bottom button position when
    // there is a change in compose height like when a compose banner is displayed.
    const update_compose_max_height = new ResizeObserver(resize.reset_compose_message_max_height);
    update_compose_max_height.observe(document.querySelector("#compose"));

    upload.feature_check($("#compose .compose_upload_file"));

    function get_input_info(event) {
        const $edit_banners_container = $(event.target).closest(".edit_form_banners");
        const is_edit_input = Boolean($edit_banners_container.length);
        const $banner_container = $edit_banners_container.length
            ? $edit_banners_container
            : $("#compose_banners");
        return {is_edit_input, $banner_container};
    }

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.wildcard_warning,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container, is_edit_input} = get_input_info(event);
            const $row = $(event.target).closest(".message_row");
            compose_validate.clear_wildcard_warnings($banner_container);
            compose_validate.set_user_acknowledged_wildcard_flag(true);
            if (is_edit_input) {
                message_edit.save_message_row_edit($row);
            } else if (event.target.dataset.validationTrigger === "schedule") {
                scheduled_messages_popover.open_send_later_menu();

                // We need to set this flag to true here because `open_send_later_menu` validates the message and sets
                // the user acknowledged wildcard flag back to 'false' and we don't want that to happen because then it
                // would again show the wildcard warning banner when we actually send the message from 'send-later' modal.
                compose_validate.set_user_acknowledged_wildcard_flag(true);
            } else {
                compose.finish();
            }
        },
    );

    const user_not_subscribed_selector = `.${CSS.escape(
        compose_banner.CLASSNAMES.user_not_subscribed,
    )}`;
    $("body").on(
        "click",
        `${user_not_subscribed_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const stream_id = compose_state.stream_id();
            if (stream_id === undefined) {
                return;
            }
            const sub = stream_data.get_sub_by_id(stream_id);
            stream_settings_components.sub_or_unsub(sub);
            $(user_not_subscribed_selector).remove();
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(compose_banner.CLASSNAMES.topic_resolved)} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            message_edit.with_first_message_id(stream_id, topic_name, (message_id) => {
                message_edit.toggle_resolve_topic(message_id, topic_name, true);
                compose_validate.clear_topic_resolved_warning(true);
            });
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unmute_topic_notification,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic_name,
                user_topics.all_visibility_policies.UNMUTED,
                false,
                true,
            );
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.automatic_new_visibility_policy,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            window.location.href = "/#settings/notifications";
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unscheduled_message,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const send_at_timestamp = scheduled_messages.get_selected_send_later_timestamp();
            scheduled_messages_popover.do_schedule_message(send_at_timestamp);
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.recipient_not_subscribed,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container} = get_input_info(event);
            const $invite_row = $(event.target).parents(".main-view-banner");

            const user_id = Number.parseInt($invite_row.data("user-id"), 10);
            const stream_id = Number.parseInt($invite_row.data("stream-id"), 10);

            function success() {
                $invite_row.remove();
            }

            function xhr_failure(xhr) {
                let error_message = "Failed to subscribe user!";
                if (xhr.responseJSON?.msg) {
                    error_message = xhr.responseJSON.msg;
                }
                compose.clear_invites();
                compose_banner.show_error_message(
                    error_message,
                    compose_banner.CLASSNAMES.generic_compose_error,
                    $banner_container,
                    $("#compose-textarea"),
                );
                $(event.target).prop("disabled", true);
            }

            const sub = sub_store.get(stream_id);

            subscriber_api.add_user_ids_to_stream([user_id], sub, success, xhr_failure);
        },
    );

    for (const classname of Object.values(compose_banner.CLASSNAMES)) {
        const classname_selector = `.${CSS.escape(classname)}`;
        $("body").on("click", `${classname_selector} .main-view-banner-close-button`, (event) => {
            event.preventDefault();
            $(event.target).parents(classname_selector).remove();
        });
    }

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", ".compose_upload_file", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $("#compose .file_input").trigger("click");
    });

    $("body").on("click", ".video_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_video_chat_button = compose_call.compute_show_video_chat_button();

        if (!show_video_chat_button) {
            return;
        }

        compose_call_ui.generate_and_insert_audio_or_video_call_link($(e.target), false);
    });

    $("body").on("click", ".audio_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_audio_chat_button = compose_call.compute_show_audio_chat_button();

        if (!show_audio_chat_button) {
            return;
        }

        compose_call_ui.generate_and_insert_audio_or_video_call_link($(e.target), true);
    });

    $("body").on("click", ".time_pick", (e) => {
        e.preventDefault();
        e.stopPropagation();

        let $target_textarea;
        let edit_message_id;
        const compose_click_target = compose_ui.get_compose_click_target(e);
        if ($(compose_click_target).parents(".message_edit_form").length === 1) {
            edit_message_id = rows.id($(compose_click_target).parents(".message_row"));
            $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
        } else {
            $target_textarea = $(compose_click_target).closest("form").find("textarea");
        }

        if (!flatpickr.is_open()) {
            const on_timestamp_selection = (val) => {
                const timestr = `<time:${val}> `;
                compose_ui.insert_syntax_and_focus(timestr, $target_textarea);
            };

            flatpickr.show_flatpickr(
                $(compose_click_target)[0],
                on_timestamp_selection,
                get_timestamp_for_flatpickr(),
                {
                    // place the time picker wherever there is space and center it horizontally
                    position: "auto center",
                    // Since we want to handle close of flatpickr manually, we don't want
                    // flatpickr to hide automatically on clicking its trigger element.
                    ignoredFocusElements: [e.currentTarget],
                },
            );
        } else {
            flatpickr.flatpickr_instance?.close();
        }
    });

    $("body").on("click", ".compose_control_button_container:not(.disabled) .add-poll", (e) => {
        e.preventDefault();
        e.stopPropagation();

        function validate_input() {
            const question = $("#poll-question-input").val().trim();

            if (question === "") {
                ui_report.error(
                    $t_html({defaultMessage: "Please enter a question."}),
                    undefined,
                    $("#dialog_error"),
                );
                return false;
            }
            return true;
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Create a poll"}),
            html_body: render_add_poll_modal(),
            html_submit_button: $t_html({defaultMessage: "Add poll"}),
            close_on_submit: true,
            on_click(e) {
                // frame a message using data input in modal, then populate the compose textarea with it
                e.preventDefault();
                e.stopPropagation();
                const poll_message_content = poll_modal.frame_poll_message_content();
                compose_ui.insert_syntax_and_focus(poll_message_content);
            },
            validate_input,
            form_id: "add-poll-form",
            id: "add-poll-modal",
            post_render: poll_modal.poll_options_setup,
            help_link: "https://zulip.com/help/create-a-poll",
        });
    });

    $("#compose").on("click", ".markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Disable unneeded compose_control_buttons as we don't
        // need them in preview mode.
        $("#compose").addClass("preview_mode");
        $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", -1);

        const content = $("#compose-textarea").val();
        $("#compose-textarea").hide();
        $("#compose .markdown_preview").hide();
        $("#compose .undo_markdown_preview").show();
        $("#compose .undo_markdown_preview").trigger("focus");
        $("#compose .preview_message_area").show();

        compose.render_and_show_preview(
            $("#compose .markdown_preview_spinner"),
            $("#compose .preview_content"),
            content,
        );
    });

    $("#compose").on("click", ".undo_markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose.clear_preview_area();
    });

    $("#compose").on("click", ".expand_composebox_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_full_size();
    });

    $("#compose").on("click", ".narrow_to_compose_recipients", (e) => {
        e.preventDefault();
        narrow.to_compose_target();
    });

    $("#compose").on("click", ".collapse_composebox_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_original_size();
    });

    $("#compose-textarea").on("focus", () => {
        compose_recipient.update_placeholder_text();
    });

    $("#compose_recipient_box").on("click", "#recipient_box_clear_topic_button", () => {
        const $input = $("#stream_message_recipient_topic");
        const $button = $("#recipient_box_clear_topic_button");

        $input.val("");
        $input.trigger("focus");
        $button.hide();
    });

    $("#compose_recipient_box").on("input", "#stream_message_recipient_topic", (e) => {
        const $button = $("#recipient_box_clear_topic_button");
        const value = $(e.target).val();
        if (value.length === 0) {
            $button.hide();
        } else {
            $button.show();
        }
    });

    $("#stream_message_recipient_topic").on("focus", () => {
        compose_recipient.update_placeholder_text();
    });

    $("#stream_message_recipient_topic").on("input", () => {
        compose_recipient.update_placeholder_text();
    });

    $("body").on("click", ".formatting_button", (e) => {
        const $compose_click_target = $(compose_ui.get_compose_click_target(e));
        const $textarea = $compose_click_target.closest("form").find("textarea");
        const format_type = $(e.target).attr("data-format-type");
        compose_ui.format_text($textarea, format_type);
        popovers.hide_all();
        $textarea.trigger("focus");
        e.preventDefault();
        e.stopPropagation();
    });

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose_actions.start("stream", {topic: page_params.narrow_topic});
        } else {
            compose_actions.start("stream", {});
        }
    }
}
