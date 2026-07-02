import $ from "jquery";

import * as overlays from "./overlays.ts";

// Unified attachment type — represents any navigable attachment in the message list.
export type AttachmentType = "image" | "video" | "file" | "unsupported";

// Renderers for the different viewers we can navigate to. These are
// registered by file_attachment_preview at startup so that this module
// doesn't import file_attachment_preview or lightbox directly, which
// would create an import cycle (both of those import this module).
type NavigationRenderers = {
    should_preview: (url: string) => boolean;
    open_file_preview: (url: string, filename: string) => void;
    open_download_only: (url: string, filename: string) => void;
    open_media_lightbox: ($el: JQuery<HTMLImageElement | HTMLMediaElement>) => void;
};

let renderers: NavigationRenderers | undefined;

export function register_navigation_renderers(r: NavigationRenderers): void {
    renderers = r;
}

export type Attachment = {
    type: AttachmentType;
    url: string;
    filename: string;
    // For images/videos, the DOM element needed to open the lightbox.
    $element?: JQuery<HTMLImageElement | HTMLMediaElement>;
};

let attachment_list: Attachment[] = [];
let current_index = -1;
// When true, start_navigation() preserves the current index instead of re-searching.
// Set by navigate_to() to avoid findIndex returning the wrong match for duplicate URLs.
let skip_next_search = false;

function get_extension(filename: string): string {
    const dot_index = filename.lastIndexOf(".");
    if (dot_index === -1) {
        return "";
    }
    return filename.slice(dot_index + 1).toLowerCase();
}

// Collect all attachments from the focused message list in DOM order.
export function collect_attachments(): Attachment[] {
    const attachments: Attachment[] = [];

    // Walk through all messages in DOM order and collect attachments
    const $message_list = $(".focused-message-list");
    if ($message_list.length === 0) {
        return attachments;
    }

    // Find all message rows and collect their attachments in order
    $message_list.find(".message_row").each(function () {
        const $row = $(this);

        // Collect inline images
        $row.find<HTMLImageElement>(
            ".message-media-inline-image img, .message-media-preview-image img",
        ).each(function () {
            const $img = $(this);
            const $anchor = $img.parent("a");
            const url = $anchor.attr("href") ?? $img.attr("src") ?? "";
            const title = $anchor.attr("aria-label") ?? url.split("/").pop() ?? "image";
            attachments.push({
                type: "image",
                url,
                filename: title,
                $element: $img,
            });
        });

        // Collect inline videos
        $row.find<HTMLMediaElement>(".message_inline_video video").each(function () {
            const $video = $(this);
            const url = $video.attr("src") ?? "";
            const filename = url.split("/").pop() ?? "video";
            attachments.push({
                type: "video",
                url,
                filename,
                $element: $video,
            });
        });

        // Collect file attachments (links to /user_uploads/)
        $row.find('a[href^="/user_uploads/"]').each(function () {
            const $link = $(this);
            const href = $link.attr("href") ?? "";

            // Skip links that are inside image/video containers (already captured above)
            if (
                $link.closest(
                    ".message-media-inline-image, .message-media-preview-image, .message_inline_video",
                ).length > 0
            ) {
                return;
            }

            const filename = decodeURIComponent(href.slice(href.lastIndexOf("/") + 1));
            const ext = get_extension(filename);

            // Skip image/video extensions since those render inline
            const image_exts = new Set([
                "jpg",
                "jpeg",
                "png",
                "gif",
                "webp",
                "svg",
                "bmp",
                "ico",
                "heic",
            ]);
            const video_exts = new Set(["mp4", "webm", "ogg", "mov"]);
            if (image_exts.has(ext) || video_exts.has(ext)) {
                return;
            }

            attachments.push({
                type: renderers?.should_preview(href) ? "file" : "unsupported",
                url: href,
                filename,
            });
        });
    });

    return attachments;
}

// Set up navigation for the current attachment being viewed.
export function start_navigation(url: string): void {
    // If navigating internally (via prev/next), we already know the index.
    // Skip the URL search to avoid matching the wrong duplicate.
    if (skip_next_search) {
        skip_next_search = false;
        return;
    }

    attachment_list = collect_attachments();

    // Find the current attachment by matching URL
    current_index = attachment_list.findIndex(
        (a) => a.url === url || a.url === decodeURIComponent(url),
    );

    if (current_index === -1) {
        // If we can't find it, try matching by filename
        const filename = decodeURIComponent(url.slice(url.lastIndexOf("/") + 1));
        current_index = attachment_list.findIndex((a) => a.filename === filename);
    }
}

export function get_total(): number {
    return attachment_list.length;
}

export function get_current_index(): number {
    return current_index;
}

export function has_prev(): boolean {
    return attachment_list.length > 1;
}

export function has_next(): boolean {
    return attachment_list.length > 1;
}

function navigate_to(index: number): void {
    if (attachment_list.length === 0) {
        return;
    }

    // Wrap around
    if (index < 0) {
        index = attachment_list.length - 1;
    } else if (index >= attachment_list.length) {
        index = 0;
    }

    if (renderers === undefined) {
        return;
    }

    const target = attachment_list[index]!;
    current_index = index;

    // Tell start_navigation() not to re-search — we already know the index.
    // This prevents findIndex from matching a duplicate URL/filename.
    skip_next_search = true;

    // Close the current overlay
    if (overlays.any_active()) {
        overlays.close_active();
    }

    // Open the appropriate viewer for the target attachment
    switch (target.type) {
        case "image":
        case "video":
            if (target.$element && target.$element.length > 0) {
                renderers.open_media_lightbox(target.$element);
            }
            break;
        case "file":
            renderers.open_file_preview(target.url, target.filename);
            break;
        case "unsupported":
            renderers.open_download_only(target.url, target.filename);
            break;
    }
}

export function prev(): void {
    if (current_index === -1 || attachment_list.length <= 1) {
        return;
    }
    navigate_to(current_index - 1);
}

export function next(): void {
    if (current_index === -1 || attachment_list.length <= 1) {
        return;
    }
    navigate_to(current_index + 1);
}

export function clear(): void {
    attachment_list = [];
    current_index = -1;
    skip_next_search = false;
}
