import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_message_edit_history from "../templates/message_edit_history.hbs";
import render_message_history_overlay from "../templates/message_history_overlay.hbs";

import {exit_overlay} from "./browser_history.ts";
import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as lightbox from "./lightbox.ts";
import * as loading from "./loading.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as messages_overlay_ui from "./messages_overlay_ui.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as rows from "./rows.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import * as spectators from "./spectators.ts";
import {realm} from "./state_data.ts";
import {get_recipient_bar_color} from "./stream_color.ts";
import {get_color} from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

type EditHistoryEntry = {
    initial_entry_for_move_history: boolean;
    edited_at_time: string;
    edited_by_notice: string;
    timestamp: number; // require to set data-message-id for overlay message row
    is_stream: boolean;
    recipient_bar_color: string | undefined;
    body_to_render: string | undefined;
    topic_edited: boolean | undefined;
    prev_topic_display_name: string | undefined;
    new_topic_display_name: string | undefined;
    is_empty_string_prev_topic: boolean | undefined;
    is_empty_string_new_topic: boolean | undefined;
    stream_changed: boolean | undefined;
    prev_stream: string | undefined;
    prev_stream_id: number | undefined;
    new_stream: string | undefined;
};

const server_message_history_schema = z.object({
    message_history: z.array(
        z.object({
            content: z.string(),
            rendered_content: z.string(),
            timestamp: z.number(),
            topic: z.string(),
            user_id: z.nullable(z.number()),
            prev_topic: z.optional(z.string()),
            stream: z.optional(z.number()),
            prev_stream: z.optional(z.number()),
            prev_content: z.optional(z.string()),
            prev_rendered_content: z.optional(z.string()),
            content_html_diff: z.optional(z.string()),
        }),
    ),
});

// Helper function to get file-type-specific placeholder text for deleted files.
function get_deleted_file_placeholder_text(mime_type: string | undefined): string {
    if (!mime_type) {
        return $t({defaultMessage: "This file does not exist or has been deleted."});
    }

    if (mime_type.startsWith("image/")) {
        return $t({defaultMessage: "This image does not exist or has been deleted."});
    }

    if (mime_type.startsWith("video/")) {
        return $t({defaultMessage: "This video does not exist or has been deleted."});
    }

    if (mime_type.startsWith("audio/")) {
        return $t({defaultMessage: "This audio does not exist or has been deleted."});
    }

    if (mime_type === "application/pdf") {
        return $t({defaultMessage: "This pdf file does not exist or has been deleted."});
    }

    return $t({defaultMessage: "This file does not exist or has been deleted."});
}

// Helper function to get placeholder text based on URL extension (for links without MIME type).
function get_deleted_file_placeholder_text_from_url(url: string | undefined): string {
    if (!url) {
        return $t({defaultMessage: "This file does not exist or has been deleted."});
    }

    const urlLower = url.toLowerCase();

    // Video Detection
    const videoExtensions = [".mp4", ".webm", ".mov", ".avi", ".mkv"];
    if (videoExtensions.some((ext) => urlLower.endsWith(ext))) {
        return $t({defaultMessage: "This video does not exist or has been deleted."});
    }

    // Image Detection
    const imageExtensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg"];
    if (imageExtensions.some((ext) => urlLower.endsWith(ext))) {
        return $t({defaultMessage: "This image does not exist or has been deleted."});
    }

    // Audio Detection
    const audioExtensions = [".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"];
    if (audioExtensions.some((ext) => urlLower.endsWith(ext))) {
        return $t({defaultMessage: "This audio does not exist or has been deleted."});
    }

    // PDF Detection
    if (urlLower.endsWith(".pdf")) {
        return $t({defaultMessage: "This pdf file does not exist or has been deleted."});
    }

    // Generic file for all other types
    return $t({defaultMessage: "This file does not exist or has been deleted."});
}

// Helper function to get the appropriate placeholder image path for deleted files.
// Returns the path to the placeholder image based on file type detection.
function get_deleted_file_placeholder_image(
    mime_type: string | undefined,
    parentHref: string | undefined,
): string {
    // Check parentHref first (most reliable for thumbnails/previews)
    // Video Detection: Check if parentHref ends with video extensions
    const videoExtensions = [".mp4", ".webm", ".mov", ".avi", ".mkv"];
    const isVideoByExtension = videoExtensions.some((ext) =>
        parentHref?.toLowerCase().endsWith(ext),
    );

    if (isVideoByExtension) {
        return "/static/images/errors/video-not-exist.png";
    }

    // Image Detection: Check if parentHref ends with image extensions
    // This catches deleted images where we only have the URL (no mime type)
    const imageExtensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg"];
    const isImageByExtension = imageExtensions.some((ext) =>
        parentHref?.toLowerCase().endsWith(ext),
    );

    if (isImageByExtension) {
        return "/static/images/errors/image-not-exist.png";
    }

    // Check for other file types by extension (PDF, audio, documents, archives, etc.)
    // These should show file-not-exist.png even if the thumbnail has an image MIME type
    const otherFileExtensions = [
        ".pdf",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".flac",
        ".aac",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".rtf",
    ];
    const isOtherFileByExtension = otherFileExtensions.some((ext) =>
        parentHref?.toLowerCase().endsWith(ext),
    );

    if (isOtherFileByExtension) {
        return "/static/images/errors/file-not-exist.png";
    }

    // Fall back to MIME type detection
    // Video Detection: Check if mime_type is video
    if (mime_type?.startsWith("video/") === true) {
        return "/static/images/errors/video-not-exist.png";
    }

    // Image Detection: If mime_type starts with "image/"
    if (mime_type?.startsWith("image/") === true) {
        return "/static/images/errors/image-not-exist.png";
    }

    // Generic File Detection: For all other cases (audio by MIME type, unknown types, etc.)
    return "/static/images/errors/file-not-exist.png";
}

// This will be used to handle up and down keyws
const keyboard_handling_context: messages_overlay_ui.Context = {
    items_container_selector: "message-edit-history-container",
    items_list_selector: "message-edit-history-list",
    row_item_selector: "message-edit-message-row",
    box_item_selector: "message-edit-message-info-box",
    id_attribute_name: "data-message-edit-history-id",
    get_items_ids() {
        const edited_messages_ids: string[] = [];
        const $message_history_list: JQuery = $(
            "#message-history-overlay .message-edit-history-list",
        );
        for (const message of $message_history_list.children()) {
            const data_message_edit_history_id = $(message).attr("data-message-edit-history-id");
            assert(data_message_edit_history_id !== undefined);
            edited_messages_ids.push(data_message_edit_history_id);
        }
        return edited_messages_ids;
    },
    on_enter() {
        return;
    },
    on_delete() {
        return;
    },
};

function get_display_stream_name(stream_id: number): string {
    const stream_name = sub_store.maybe_get_stream_name(stream_id);
    if (stream_name === undefined) {
        return $t({defaultMessage: "Unknown channel"});
    }
    return stream_name;
}

function show_loading_indicator(): void {
    loading.make_indicator($(".message-edit-history-container .loading_indicator"));
    $(".message-edit-history-container .loading_indicator").addClass(
        "overlay_loading_indicator_style",
    );
}

function hide_loading_indicator(): void {
    loading.destroy_indicator($(".message-edit-history-container .loading_indicator"));
    $(".message-edit-history-container .loading_indicator").removeClass(
        "overlay_loading_indicator_style",
    );
}

export function fetch_and_render_message_history(message: Message): void {
    assert(message_lists.current !== undefined);
    const message_container = message_lists.current.view.message_containers.get(message.id);
    assert(message_container !== undefined);
    const move_history_only =
        realm.realm_message_edit_history_visibility_policy ===
        message_edit_history_visibility_policy_values.moves_only.code;
    $("#message-edit-history-overlay-container").html(
        render_message_history_overlay({
            moved: message_container.moved,
            edited: message_container.edited,
            move_history_only,
        }),
    );
    $("#message-edit-history-overlay-container").attr("data-message-id", message.id);
    open_overlay();
    show_loading_indicator();
    void channel.get({
        url: "/json/messages/" + message.id + "/history",
        data: {
            message_id: JSON.stringify(message.id),
            allow_empty_topic_name: true,
        },
        success(raw_data) {
            if (
                !overlays.message_edit_history_open() ||
                $("#message-edit-history-overlay-container").attr("data-message-id") !==
                    String(message.id)
            ) {
                return;
            }
            const data = server_message_history_schema.parse(raw_data);

            const content_edit_history: EditHistoryEntry[] = [];
            let prev_stream_item: EditHistoryEntry | null = null;
            for (const [index, msg] of data.message_history.entries()) {
                // Format times and dates nicely for display
                const time = new Date(msg.timestamp * 1000);
                const edited_at_time = timerender.get_full_datetime(time, "time");

                if (!msg.user_id) {
                    continue;
                }

                const person = people.get_user_by_id_assert_valid(msg.user_id);
                const full_name = person.full_name;

                let edited_by_notice;
                let body_to_render;
                let topic_edited;
                let prev_topic_display_name;
                let new_topic_display_name;
                let is_empty_string_prev_topic;
                let is_empty_string_new_topic;
                let stream_changed;
                let prev_stream;
                let prev_stream_id;
                let initial_entry_for_move_history = false;

                if (index === 0) {
                    edited_by_notice = $t({defaultMessage: "Posted by {full_name}"}, {full_name});
                    if (move_history_only) {
                        // If message history is limited to moves only, then we
                        // display the original topic and channel for the message.
                        initial_entry_for_move_history = true;
                        new_topic_display_name = util.get_final_topic_display_name(msg.topic);
                    } else {
                        // Otherwise, we display the original message content.
                        body_to_render = msg.rendered_content;
                    }
                } else if (msg.prev_topic !== undefined && msg.prev_content) {
                    edited_by_notice = $t({defaultMessage: "Edited by {full_name}"}, {full_name});
                    body_to_render = msg.content_html_diff;
                    topic_edited = true;
                    prev_topic_display_name = util.get_final_topic_display_name(msg.prev_topic);
                    new_topic_display_name = util.get_final_topic_display_name(msg.topic);
                    is_empty_string_prev_topic = msg.prev_topic === "";
                    is_empty_string_new_topic = msg.topic === "";
                } else if (msg.prev_topic !== undefined && msg.prev_stream) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic_display_name = util.get_final_topic_display_name(msg.prev_topic);
                    new_topic_display_name = util.get_final_topic_display_name(msg.topic);
                    is_empty_string_prev_topic = msg.prev_topic === "";
                    is_empty_string_new_topic = msg.topic === "";
                    stream_changed = true;
                    prev_stream_id = msg.prev_stream;
                    prev_stream = get_display_stream_name(msg.prev_stream);
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = get_display_stream_name(msg.prev_stream);
                    }
                } else if (msg.prev_topic !== undefined) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    topic_edited = true;
                    prev_topic_display_name = util.get_final_topic_display_name(msg.prev_topic);
                    new_topic_display_name = util.get_final_topic_display_name(msg.topic);
                    is_empty_string_prev_topic = msg.prev_topic === "";
                    is_empty_string_new_topic = msg.topic === "";
                } else if (msg.prev_stream) {
                    edited_by_notice = $t({defaultMessage: "Moved by {full_name}"}, {full_name});
                    stream_changed = true;
                    prev_stream_id = msg.prev_stream;
                    prev_stream = get_display_stream_name(msg.prev_stream);
                    if (prev_stream_item !== null) {
                        prev_stream_item.new_stream = get_display_stream_name(msg.prev_stream);
                    }
                } else {
                    // just a content edit
                    edited_by_notice = $t({defaultMessage: "Edited by {full_name}"}, {full_name});
                    body_to_render = msg.content_html_diff;
                }
                const item: EditHistoryEntry = {
                    initial_entry_for_move_history,
                    edited_at_time,
                    edited_by_notice,
                    timestamp: msg.timestamp,
                    is_stream: message.is_stream,
                    recipient_bar_color: undefined,
                    body_to_render,
                    topic_edited,
                    prev_topic_display_name,
                    new_topic_display_name,
                    is_empty_string_prev_topic,
                    is_empty_string_new_topic,
                    stream_changed,
                    prev_stream,
                    prev_stream_id,
                    new_stream: undefined,
                };

                if (msg.prev_stream) {
                    prev_stream_item = item;
                }

                content_edit_history.push(item);
            }
            if (prev_stream_item !== null) {
                assert(message.type === "stream");
                prev_stream_item.new_stream = get_display_stream_name(message.stream_id);
            }

            // In order to correctly compute the recipient_bar_color
            // values, it is convenient to iterate through the array of edit history
            // entries in reverse chronological order.
            if (message.is_stream) {
                // Start with the message's current location.
                let stream_display_name: string = get_display_stream_name(message.stream_id);
                let stream_color: string = get_color(message.stream_id);
                let recipient_bar_color: string = get_recipient_bar_color(stream_color);
                for (const edit_history_entry of content_edit_history.toReversed()) {
                    // The stream following this move is the one whose color we already have.
                    edit_history_entry.recipient_bar_color = recipient_bar_color;
                    if (edit_history_entry.stream_changed) {
                        // If this event moved the message, then immediately
                        // prior to this event, the message must have been in
                        // edit_history_event.prev_stream_id; fetch its color.
                        assert(edit_history_entry.prev_stream_id !== undefined);
                        stream_display_name = get_display_stream_name(
                            edit_history_entry.prev_stream_id,
                        );
                        stream_color = get_color(edit_history_entry.prev_stream_id);
                        recipient_bar_color = get_recipient_bar_color(stream_color);
                    }
                }
                if (move_history_only) {
                    // If message history is limited to moves only, then we
                    // display the original topic and channel for the message.
                    content_edit_history[0]!.new_stream = stream_display_name;
                }
            }
            const rendered_list_html = render_message_edit_history({
                edited_messages: content_edit_history,
            });
            $("#message-history-overlay").attr("data-message-id", message.id);
            hide_loading_indicator();
            $("#message-history-overlay .overlay-messages-list").append($(rendered_list_html));

            // Pass the history through rendered_markdown.ts
            // to update dynamic_elements in the content.
            $("#message-history-overlay")
                .find(".rendered_markdown")
                .each(function () {
                    rendered_markdown.update_elements($(this));
                });

            // When an image is deleted before thumbnailing is completed, we can
            // end up with the loading spinner HTML syntax stuck in message edit
            // history indefinitely. Mask this by replacing thumbnailing loading
            // spinners in edit history with the deleted image placeholder.
            $("#message-history-overlay")
                .find("img.image-loading-placeholder")
                .each(function () {
                    const $img = $(this);
                    $img.attr("src", "/static/images/errors/image-not-exist.png");
                    $img.attr(
                        "alt",
                        $t({defaultMessage: "This file does not exist or has been deleted."}),
                    );
                    $img.removeClass("image-loading-placeholder");
                });

            // Handle all media that fail to load (404 errors) in the message edit history.
            // This catches images that were previously valid but have since been deleted.
            $("#message-history-overlay")
                .find(".rendered_markdown img, .rendered_markdown video")
                .on("error", function () {
                    const $element = $(this);

                    // Safety check: prevent infinite loops.
                    const currentSrc = $element.attr("src");
                    if (
                        currentSrc?.includes("image-not-exist.png") ||
                        currentSrc?.includes("video-not-exist.png") ||
                        currentSrc?.includes("file-not-exist.png")
                    ) {
                        return;
                    }

                    // HANDLE VIDEO PLAYERS:
                    // If the broken element is a <video> tag, we must replace the whole player
                    // with the static "video-not-exist" image.
                    if ($element.is("video")) {
                        const placeholder_text = $t({
                            defaultMessage: "This video does not exist or has been deleted.",
                        });
                        const $newImg = $("<img>")
                            .attr("src", "/static/images/errors/video-not-exist.png")
                            .attr("alt", placeholder_text)
                            .attr("title", placeholder_text)
                            .addClass("message_edit_history_content"); // Keep consistent styling

                        $element.replaceWith($newImg);
                        return;
                    }

                    // HANDLE IMAGES (Existing Logic):
                    // Get the MIME type from the data attribute and parent link href for file type detection.
                    const mime_type = $element.attr("data-original-content-type");
                    const parentHref = $element.closest("a").attr("href");

                    // Determine the appropriate placeholder image based on file type.
                    const placeholder_image = get_deleted_file_placeholder_image(
                        mime_type,
                        parentHref,
                    );

                    // Get the appropriate placeholder text for accessibility.
                    const placeholder_text = get_deleted_file_placeholder_text(mime_type);

                    // Replace the broken image with the appropriate placeholder and set text.
                    $element.attr("src", placeholder_image);
                    $element.attr("alt", placeholder_text);
                    $element.attr("title", placeholder_text);

                    // Remove the loading placeholder class if it exists.
                    $element.removeClass("image-loading-placeholder");
                });

            // HANDLE DELETED FILE LINKS (PDFs, documents, audio, etc.):
            // These are rendered as text links (<a href="/user_uploads/...">filename.pdf</a>)
            // and don't fire "error" events, so we must check them manually.
            // We ignore links that already contain images/videos/placeholders to prevent double replacement.
            $("#message-history-overlay")
                .find(".rendered_markdown a[href^='/user_uploads/']")
                .filter(function () {
                    const $link = $(this);
                    const url = $link.attr("href");

                    if (!url) {
                        return false;
                    }

                    // Exclude links that point to images or videos - these are handled by the error handler
                    const urlLower = url.toLowerCase();
                    const videoExtensions = [".mp4", ".webm", ".mov", ".avi", ".mkv"];
                    const imageExtensions = [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".gif",
                        ".webp",
                        ".bmp",
                        ".tiff",
                        ".svg",
                    ];

                    const isVideo = videoExtensions.some((ext) => urlLower.endsWith(ext));
                    const isImage = imageExtensions.some((ext) => urlLower.endsWith(ext));

                    // Only process links that:
                    // 1. Don't point to images/videos (those are handled by error handler)
                    // 2. Don't already contain media elements or placeholders
                    return (
                        !isVideo &&
                        !isImage &&
                        $link.find("img").length === 0 &&
                        $link.find("video").length === 0 &&
                        $link.find(".message_edit_history_content").length === 0
                    );
                })
                .each(function () {
                    const $link = $(this);
                    const url = $link.attr("href");

                    if (!url) {
                        return;
                    }

                    // Check if the file exists using a lightweight HEAD request
                    void (async () => {
                        try {
                            const response = await fetch(url, {method: "HEAD"});
                            if (response.status === 404) {
                                // The file is gone. Determine the appropriate placeholder based on file type.
                                const placeholder_image = get_deleted_file_placeholder_image(
                                    undefined,
                                    url,
                                );
                                const placeholder_text =
                                    get_deleted_file_placeholder_text_from_url(url);

                                const $newImg = $("<img>")
                                    .attr("src", placeholder_image)
                                    .attr("alt", placeholder_text)
                                    .attr("title", placeholder_text)
                                    .addClass("message_edit_history_content"); // Keep consistent styling

                                $link.replaceWith($newImg);
                            }
                        } catch {
                            // If the check fails (e.g. network error), leave the link alone.
                        }
                    })();
                });

            const first_element_id = content_edit_history[0]!.timestamp;
            messages_overlay_ui.set_initial_element(
                String(first_element_id),
                keyboard_handling_context,
            );
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Error fetching message edit history."}),
                xhr,
                $("#message-history-overlay #message-history-error"),
            );
            hide_loading_indicator();
            $("#message-history-error").show();
        },
    });
}

export function open_overlay(): void {
    if (overlays.any_active()) {
        return;
    }
    overlays.open_overlay({
        name: "message_edit_history",
        $overlay: $("#message-history-overlay"),
        on_close() {
            exit_overlay();
            $("#message-edit-history-overlay-container").empty();
        },
    });
}

export function handle_keyboard_events(event_key: string): void {
    messages_overlay_ui.modals_handle_events(event_key, keyboard_handling_context);
}

export function initialize(): void {
    $("body").on("mouseenter", ".message_edit_notice, .edit-notifications", (e) => {
        if (
            realm.realm_message_edit_history_visibility_policy !==
            message_edit_history_visibility_policy_values.never.code
        ) {
            $(e.currentTarget).addClass("message_edit_notice_hover");
        }
    });

    $("body").on("mouseleave", ".message_edit_notice, .edit-notifications", (e) => {
        if (
            realm.realm_message_edit_history_visibility_policy !==
            message_edit_history_visibility_policy_values.never.code
        ) {
            $(e.currentTarget).removeClass("message_edit_notice_hover");
        }
    });

    $("body").on(
        "click",
        ".message_edit_notice, .edit-notifications",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            e.preventDefault();

            const message_id = rows.id($(this).closest(".message_row"));
            assert(message_lists.current !== undefined);
            const $row = message_lists.current.get_row(message_id);
            const row_id = rows.id($row);
            const message = message_lists.current.get(row_id);
            assert(message !== undefined);

            if (page_params.is_spectator) {
                spectators.login_to_access();
                return;
            }

            if (
                realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.always.code ||
                (realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.moves_only.code &&
                    message.last_moved_timestamp !== undefined)
            ) {
                fetch_and_render_message_history(message);
                $("#message-history-overlay .exit-sign").trigger("focus");
            }
        },
    );

    $("body").on(
        "focus",
        "#message-history-overlay .overlay-message-info-box",
        function (this: HTMLElement) {
            messages_overlay_ui.activate_element(this, keyboard_handling_context);
        },
    );

    $("body").on("click", "#message-history-overlay .message_edit_history_content", (e) => {
        const $img = $(e.target).closest("img");
        if ($img.length > 0) {
            e.stopPropagation();
            e.preventDefault();
            overlays.close_overlay("message_edit_history");
            lightbox.handle_inline_media_element_click($img, true);
            return;
        }

        const $video = $(e.target).closest("video");
        if ($video.length > 0) {
            e.stopPropagation();
            e.preventDefault();
            overlays.close_overlay("message_edit_history");
            lightbox.handle_inline_media_element_click($video, true);
        }
    });
}
