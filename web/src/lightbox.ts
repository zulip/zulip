import $ from "jquery";
import assert from "minimalistic-assert";
import panzoom from "panzoom";
import type {PanZoom} from "panzoom";

import render_lightbox_overlay from "../templates/lightbox_overlay.hbs";

import * as blueslip from "./blueslip.ts";
import * as message_store from "./message_store.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as popovers from "./popovers.ts";
import * as rows from "./rows.ts";
import * as util from "./util.ts";

type MediaType = "image" | "inline-video" | "youtube-video" | "vimeo-video" | "embed-video";

type Media = {
    // Sender's full name
    user: string | undefined;
    // aria-label (or url, as fallback) of media
    title: string;
    type: MediaType;
    // URL to use in message list or carousel
    preview: string;
    // URL to use for display in the lightbox
    source: string;
    // URL to the original resource for download
    url: string;
    original_width_px: number | undefined;
    original_height_px: number | undefined;
};

let is_open = false;

// The asset map is a map of all retrieved images and YouTube videos that are memoized instead of
// being looked up multiple times. It is keyed by the message id with each value being the
// message's assets map keyed by the asset's "canonical URL," which is likely the `src` used in
// the message feed, but for thumbnailed images is the full-resolution original URL.
const asset_map = new Map<number, Map<string, Media>>();

export class PanZoomControl {
    // Class for both initializing and controlling the
    // the pan/zoom functionality.
    container: HTMLElement;
    panzoom: PanZoom;
    constructor(container: HTMLElement) {
        this.container = container;
        this.panzoom = panzoom(this.container, {
            smoothScroll: false,
            // Ideally we'd set `bounds` here, but that feature is
            // currently broken upstream.  See
            // https://github.com/anvaka/panzoom/issues/112.
            maxZoom: 64,
            minZoom: 1 / 16,
            filterKey() {
                // Disable the library's built in keybindings
                return true;
            },
        });
        // The following events are necessary to prevent the click event
        // firing where the user "unclicks" at the end of the drag, which
        // was causing accidental overlay closes in some situations.
        this.panzoom.on("pan", () => {
            // Marks this overlay as needing to stay open.
            $("#lightbox_overlay").data("noclose", true);

            // Enable the panzoom reset button.
            $("#lightbox_overlay .lightbox-zoom-reset").removeClass("disabled");
        });

        this.panzoom.on("panend", (e: PanZoom) => {
            // Check if the image has been panned out of view.
            this.constrainImage(e);

            // Don't remove the noclose attribute on this overlay until after paint,
            // otherwise it will be removed too early and close the lightbox
            // unintentionally.
            setTimeout(() => {
                $("#lightbox_overlay").data("noclose", false);
            }, 0);
        });

        this.panzoom.on("zoom", (e: PanZoom) => {
            // Check if the image has been zoomed out of view.
            // We are using the zoom event instead of zoomend because the zoomend
            // event does not fire when using the scroll wheel or pinch to zoom.
            // https://github.com/anvaka/panzoom/issues/250
            this.constrainImage(e);

            // Enable the panzoom reset button.
            $("#lightbox_overlay .lightbox-zoom-reset").removeClass("disabled");
        });

        // key bindings
        document.addEventListener("keydown", (e) => {
            if (!overlays.lightbox_open()) {
                return;
            }
            switch (e.key) {
                case "Z":
                case "+":
                    this.zoomIn();
                    break;
                case "z":
                case "-":
                    this.zoomOut();
                    break;
                case "v":
                    overlays.close_overlay("lightbox");
                    break;
            }
            e.preventDefault();
            e.stopPropagation();
        });
    }

    constrainImage(e: PanZoom): void {
        if (!this.isActive()) {
            return;
        }

        // Instead of using panzoom's built in bounds option which was buggy
        // at the time of this writing, we act on pan/zoom events and move the
        // image back in to view if it is moved beyond the image-preview container.
        // See https://github.com/anvaka/panzoom/issues/112 for upstream discussion.

        const {scale, x, y} = e.getTransform();
        const image_width = util.the($(".zoom-element > img")).clientWidth * scale;
        const image_height = util.the($(".zoom-element > img")).clientHeight * scale;
        const zoom_element_width = util.the($(".zoom-element")).clientWidth * scale;
        const zoom_element_height = util.the($(".zoom-element")).clientHeight * scale;
        const max_translate_x = util.the($(".image-preview")).clientWidth;
        const max_translate_y = util.the($(".image-preview")).clientHeight;

        // When the image is dragged out of the image-preview container
        // (max_translate) it will be "snapped" back so that the number
        // of pixels set below will remain visible in the dimension it was dragged.
        const return_buffer = 50 * scale;
        // Move the image if it gets within this many pixels of the edge.
        const border = 20;

        const zoom_border_width = (zoom_element_width - image_width) / 2 + image_width;
        const zoom_border_height = (zoom_element_height - image_height) / 2 + image_height;
        const modified_x = x + zoom_border_width;
        const modified_y = y + zoom_border_height;

        if (modified_x < 0 + border) {
            // Image has been dragged beyond the LEFT of the view.
            const move_by = modified_x * -1;
            e.moveBy(move_by + return_buffer, 0, false);
        } else if (modified_x - image_width > max_translate_x - border) {
            // Image has been dragged beyond the RIGHT of the view.
            const move_by = modified_x - max_translate_x - image_width;
            e.moveBy(-move_by - return_buffer, 0, false);
        }

        if (modified_y < 0 + border) {
            // Image has been dragged beyond the TOP of the view.
            const move_by = modified_y * -1;
            e.moveBy(0, move_by + return_buffer, false);
        } else if (modified_y - image_height > max_translate_y - border) {
            // Image has been dragged beyond the BOTTOM of the view.
            const move_by = modified_y - max_translate_y - image_height;
            e.moveBy(0, -move_by - return_buffer, false);
        }
    }

    reset(): void {
        // To reset the panzoom state, we want to:
        // Reset zoom to the initial state.
        this.panzoom.zoomAbs(0, 0, 1);
        // Re-center the image.
        this.panzoom.moveTo(0, 0);
        // Always ensure that the overlay is available for click to close.
        // This way we don't rely on the above events firing panend,
        // of which there is some anecdotal evidence that suggests they
        // might be prone to race conditions.
        $("#lightbox_overlay").data("noclose", false);
        // Disable the lightbox reset button to reflect the state that
        // the image has not been panned or zoomed.
        $("#lightbox_overlay .lightbox-zoom-reset").addClass("disabled");
    }

    zoomIn(): void {
        if (!this.isActive()) {
            return;
        }

        const w = $(".image-preview").width()!;
        const h = $(".image-preview").height()!;
        this.panzoom.smoothZoom(w / 2, h / 2, Math.SQRT2);
    }

    zoomOut(): void {
        if (!this.isActive()) {
            return;
        }

        const w = $(".image-preview").width()!;
        const h = $(".image-preview").height()!;
        this.panzoom.smoothZoom(w / 2, h / 2, Math.SQRT1_2);
    }

    isActive(): boolean {
        return $(".image-preview .zoom-element img").length > 0;
    }
}

export function clear_for_testing(): void {
    is_open = false;
    asset_map.clear();
}

export function invalidate_asset_map_of_message(message_id: number): void {
    asset_map.delete(message_id);
}

function set_selected_media_element($media: JQuery<HTMLMediaElement | HTMLImageElement>): void {
    // Clear out any previously selected element
    $(".media-to-select-in-lightbox-list").removeClass("media-to-select-in-lightbox-list");
    $media.addClass("media-to-select-in-lightbox-list");
}

export function canonical_url_of_media(media: HTMLMediaElement | HTMLImageElement): string {
    let media_string = media.src;
    if (!media_string) {
        return "";
    }

    const media_url = new URL(media_string);

    if (
        media_url.origin === window.location.origin &&
        media_url.pathname.startsWith("/user_uploads/thumbnail/")
    ) {
        assert(media.parentElement instanceof HTMLAnchorElement);
        media_string = media.parentElement.href;
    }

    return media_string;
}

export function render_lightbox_media_list(): void {
    if (!is_open) {
        const message_media_list = $<HTMLMediaElement | HTMLImageElement>(
            ".focused-message-list .message_inline_image img, .focused-message-list .message_inline_video video",
        ).toArray();
        const $lightbox_media_list = $("#lightbox_overlay .image-list").empty();
        for (const media of message_media_list) {
            const className = media.classList.contains("media-to-select-in-lightbox-list")
                ? "image selected"
                : "image";
            const is_video = media.tagName === "VIDEO";

            // We parse the data for each image to show in the list,
            // while we still have its original DOM element handy, so
            // that navigating within the list only needs the `src`
            // attribute used to construct the node object above.
            const payload = parse_media_data(media);

            let $node: JQuery;
            if (is_video) {
                $node = $("<div>")
                    .addClass(className)
                    .addClass("lightbox_video")
                    .attr("data-url", payload.url);

                const $video = $("<video>");
                $video.attr("src", payload.source);

                $node.append($video);
            } else {
                $node = $("<div>")
                    .addClass(className)
                    .attr("data-url", payload.url)
                    .css({
                        backgroundImage: `url(${CSS.escape(payload.preview || payload.source)})`,
                    });
            }

            $lightbox_media_list.append($node);
        }
    }
}

function display_image(payload: Media): void {
    render_lightbox_media_list();

    $(".player-container, .video-player").hide();
    $(".image-preview, .media-actions, .media-description, .download, .lightbox-zoom-reset").show();

    const $img_container = $("#lightbox_overlay .image-preview > .zoom-element");
    const $img = $("<img>");
    if (payload.preview && payload.original_width_px && payload.original_height_px) {
        $img.attr("src", payload.preview);
        $img.attr("width", payload.original_width_px);
        $img.attr("height", payload.original_height_px);
        // srcset contains the reference to the original image,
        // and will be preferred over the src image when available
        $img.attr("srcset", `${payload.source} ${payload.original_width_px}w`);
        $img.attr("sizes", "100vw");
    } else {
        $img.attr("src", payload.source);
    }
    $img_container.empty();
    $img_container.append($img).show();

    const filename = payload.url?.split("/").pop();
    $(".media-description .title")
        .text(payload.title ?? "N/A")
        .attr("aria-label", payload.title ?? "N/A")
        .attr("data-filename", filename ?? "N/A");
    if (payload.user !== undefined) {
        $(".media-description .user").text(payload.user).prop("title", payload.user);
    }

    $(".media-actions .open").attr("href", payload.url);

    const url = new URL(payload.url, window.location.href);
    const same_origin = url.origin === window.location.origin;
    if (same_origin && url.pathname.startsWith("/user_uploads/")) {
        // Switch to the "download" handler, so S3 URLs set their Content-Disposition
        url.pathname = "/user_uploads/download/" + url.pathname.slice("/user_uploads/".length);
        $(".media-actions .download").attr("href", url.href);
    } else if (same_origin) {
        $(".media-actions .download").attr("href", payload.url);
    } else {
        // If it's not same-origin, and we don't know how to tell the remote service to put a
        // content-disposition on it, the download can't possibly download, just show -- so hide the
        // element.
        $(".media-actions .download").hide();
    }
}

function display_video(payload: Media): void {
    render_lightbox_media_list();

    $(
        "#lightbox_overlay .image-preview, .media-description, .download, .lightbox-zoom-reset, .video-player",
    ).hide();
    $(".player-container").show();

    if (payload.type === "inline-video") {
        $(".player-container").hide();
        $(".video-player, .media-description").show();
        const $video = $("<video>");
        $video.attr("src", payload.source);
        $video.attr("controls", "true");
        $(".video-player").empty();
        $(".video-player").append($video);
        $(".media-actions .open").attr("href", payload.url);

        const filename = payload.url?.split("/").pop();
        $(".media-description .title")
            .text(payload.title ?? "N/A")
            .attr("aria-label", payload.title ?? "N/A")
            .attr("data-filename", filename ?? "N/A");
        if (payload.user !== undefined) {
            $(".media-description .user").text(payload.user).prop("title", payload.user);
        }
        return;
    }

    const $iframe = $("<iframe>");
    $iframe.attr(
        "sandbox",
        "allow-forms allow-modals allow-orientation-lock allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-presentation allow-same-origin allow-scripts",
    );
    assert(payload.source !== undefined);
    $iframe.attr("src", payload.source);
    $iframe.attr("frameborder", 0);
    $iframe.attr("allowfullscreen", "true");

    $("#lightbox_overlay .player-container").empty();
    $("#lightbox_overlay .player-container").append($iframe);
    $(".media-actions .open").attr("href", payload.url);
}

export function build_open_media_function(
    on_close = (): void => {
        remove_video_players();
        is_open = false;
        assert(document.activeElement instanceof HTMLElement);
        document.activeElement.blur();
    },
): ($media: JQuery<HTMLMediaElement | HTMLImageElement>) => void {
    return function ($media: JQuery<HTMLMediaElement | HTMLImageElement>): void {
        // This is used both for clicking on media in the messagelist, as well as clicking on images
        // in the media list under the lightbox when it is open.
        const payload = parse_media_data(util.the($media));

        assert(payload !== undefined);
        if (payload.type === "image") {
            display_image(payload);
        } else {
            display_video(payload);
        }
        if (is_open) {
            return;
        }

        assert(on_close !== undefined);
        overlays.open_overlay({
            name: "lightbox",
            $overlay: $("#lightbox_overlay"),
            on_close,
        });

        popovers.hide_all();
        is_open = true;
    };
}

export function show_from_selected_message(): void {
    const $message_selected = $(".selected_message");
    let $message = $message_selected;
    // This is a function to satisfy eslint unicorn/no-array-callback-reference
    const media_classes = (): string => ".message_inline_image img, .message_inline_image video";
    let $media = $message.find<HTMLMediaElement | HTMLImageElement>(media_classes());
    let $prev_traverse = false;

    // First, we walk upwards/backwards, starting with the current
    // message, looking for an media to preview.
    //
    // Care must be taken, since both recipient_row elements and
    // message_row objects have siblings of different types, such as
    // date elements.
    while ($media.length === 0) {
        if ($message.prev().length === 0) {
            const $prev_message_group = $message.parent().prevAll(".recipient_row").first();
            if ($prev_message_group.length === 0) {
                $prev_traverse = true;
                $message = $message_selected;
                break;
            } else {
                $message = rows.last_message_in_group($prev_message_group);
                $media = $message.find<HTMLMediaElement | HTMLImageElement>(media_classes());
                continue;
            }
        }
        $message = $message.prev();
        $media = $message.find<HTMLMediaElement | HTMLImageElement>(media_classes());
    }

    if ($prev_traverse) {
        while ($media.length === 0) {
            if ($message.next().length === 0) {
                const $next_message_group = $message.parent().nextAll(".recipient_row").first();
                if ($next_message_group.length === 0) {
                    break;
                } else {
                    $message = rows.first_message_in_group($next_message_group);
                    $media = $message.find<HTMLMediaElement | HTMLImageElement>(media_classes());
                    continue;
                }
            }
            $message = $message.next();
            $media = $message.find<HTMLMediaElement | HTMLImageElement>(media_classes());
        }
    }

    if ($media.length > 0) {
        const open_media = build_open_media_function(undefined);
        // Since this function is only called from the "show_lightbox"
        // hotkey, we don't have a selected image to load. Therefore,
        // we show the first one returned from the traversal above.
        set_selected_media_element($media.first());
        open_media($media.first());
    }
}

function supports_heic(): boolean {
    if (!util.is_client_safari()) {
        return false;
    }
    const match = /Version\/(\d+)/.exec(navigator.userAgent);
    if (!match?.[1]) {
        return false;
    }
    const version = Number.parseInt(match[1], 10);
    return !Number.isNaN(version) && version >= 17;
}

// retrieve the metadata from the DOM and store into the asset_map.
export function parse_media_data(media: HTMLMediaElement | HTMLImageElement): Media {
    const $media = $(media);
    const canonical_url = canonical_url_of_media(media);
    let message_id;

    // This includes the preview feature in the message-edit UI as well as compose.
    const is_compose_preview_media = $media.closest(".preview_content").length > 0;
    const $message_row = rows.get_closest_row($media);
    let use_asset_map;
    let sender_full_name;

    if (is_compose_preview_media || rows.is_overlay_row($message_row)) {
        // We don't use the asset map cache in compose/edit UIs or
        // overlays, since the content is not stable.
        sender_full_name = people.my_full_name();
        use_asset_map = false;
    } else if ($message_row.length > 0) {
        use_asset_map = true;
        message_id = rows.id($message_row);

        if (asset_map.has(message_id) && asset_map.get(message_id)?.has(canonical_url)) {
            // Use the cached value
            const payload = asset_map.get(message_id)!.get(canonical_url);
            assert(payload !== undefined);
            return payload;
        }

        const message = message_store.get(message_id);
        if (message === undefined) {
            blueslip.error("Lightbox for unknown message", {message_id});
        } else {
            sender_full_name = message.sender_full_name;
        }
    }

    // if wrapped in the .youtube-video class, it will be length = 1, and therefore
    // cast to true.
    const is_youtube_video = $media.closest(".youtube-video").length > 0;
    const is_vimeo_video = $media.closest(".vimeo-video").length > 0;
    const is_embed_video = $media.closest(".embed-video").length > 0;
    const is_inline_video = $media.closest(".message_inline_video").length > 0;

    const $parent = $media.parent();
    let type: MediaType;
    let source;
    const url = $parent.attr("href");
    assert(url !== undefined);

    let preview_src = $media.attr("src");
    const is_loading_placeholder = $media.hasClass("image-loading-placeholder");
    if (is_loading_placeholder) {
        preview_src = "";
    }
    const original_dimensions = $media.attr("data-original-dimensions");
    let original_width_px;
    let original_height_px;
    if (original_dimensions) {
        const found = /^(\d+)x(\d+)$/.exec(original_dimensions);
        if (found) {
            original_width_px = Number(found[1]);
            original_height_px = Number(found[2]);
        }
    }

    const transcoded_image = $media.attr("data-transcoded-image");

    if (is_inline_video) {
        type = "inline-video";
        // Render video from original source to reduce load on our own servers.  The `url` is the
        // non-Camo'd version; `preview` is the Camo'd URL.
        source = url;
    } else if (is_youtube_video) {
        type = "youtube-video";
        source = "https://www.youtube.com/embed/" + $parent.attr("data-id");
    } else if (is_vimeo_video) {
        type = "vimeo-video";
        source = "https://player.vimeo.com/video/" + $parent.attr("data-id");
    } else if (is_embed_video) {
        type = "embed-video";
        source =
            "data:text/html," +
            window.encodeURIComponent(
                "<!DOCTYPE html><style>iframe{position:absolute;left:0;top:0;width:100%;height:100%;box-sizing:border-box}</style>" +
                    $parent.attr("data-id"),
            );
    } else {
        type = "image";
        if ($media.attr("data-src-fullsize")) {
            source = $media.attr("data-src-fullsize");
        } else if (transcoded_image && preview_src) {
            if ($media.attr("data-original-content-type") === "image/heic" && supports_heic()) {
                // It's an HEIC and we support it -- don't use the transcoded version
                source = url;
            } else {
                source = preview_src.replace(/\/[^/]+$/, "/" + transcoded_image);
            }
        } else {
            source = url;
        }
    }

    const payload = {
        user: sender_full_name,
        title: $parent.attr("aria-label") ?? url,
        type,
        preview: preview_src && util.is_valid_url(preview_src) ? preview_src : "",
        original_width_px,
        original_height_px,
        source: source && util.is_valid_url(source) ? source : "",
        url: util.is_valid_url(url) ? url : "",
    };

    if (use_asset_map && !is_loading_placeholder && canonical_url !== "") {
        // Update the asset_map, if we had a message ID involved.
        assert(message_id !== undefined);
        if (!asset_map.has(message_id)) {
            asset_map.set(message_id, new Map<string, Media>());
        }
        asset_map.get(message_id)!.set(canonical_url, payload);
    }
    return payload;
}

export function prev(): void {
    $(".image-list .image.selected").prev().trigger("click");
}

export function next(): void {
    $(".image-list .image.selected").next().trigger("click");
}

function remove_video_players(): void {
    // Remove video players from the DOM. Used when closing lightbox
    // so that videos doesn't keep playing in the background.
    $(".player-container iframe").remove();
    $("#lightbox_overlay .video-player").html("");
}

// this is a block of events that are required for the lightbox to work.
export function initialize(): void {
    // Renders the DOM for the lightbox.
    const rendered_lightbox_overlay = render_lightbox_overlay();
    $("body").append($(rendered_lightbox_overlay));

    // Bind the pan/zoom control the newly created element.
    const pan_zoom_control = new PanZoomControl(
        util.the($("#lightbox_overlay .image-preview > .zoom-element")),
    );

    const reset_lightbox_state = function (): void {
        remove_video_players();
        is_open = false;
        assert(document.activeElement instanceof HTMLElement);
        document.activeElement.blur();
        if (pan_zoom_control.isActive()) {
            pan_zoom_control.reset();
        }
    };

    const open_image = build_open_media_function(reset_lightbox_state);
    const open_video = build_open_media_function(undefined);

    $("#main_div, #compose .preview_content").on(
        "click",
        ".message_inline_image:not(.message_inline_video) a, .message_inline_animated_image_still",
        function (e) {
            // prevent the link from opening in a new page.
            e.preventDefault();
            // prevent the message compose dialog from happening.
            e.stopPropagation();
            const $img = $(this).find<HTMLImageElement>("img");
            set_selected_media_element($img);
            open_image($img);
        },
    );

    $("#main_div, #compose .preview_content").on("click", ".message_inline_video", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const $video = $(e.currentTarget).find<HTMLMediaElement>("video");
        set_selected_media_element($video);
        open_video($video);
    });

    $("#lightbox_overlay .download").on("click", function () {
        this.blur();
    });

    $("#lightbox_overlay").on("click", ".image-list .image", function (this: HTMLElement) {
        // Remove any video players so sound does not continue when
        // navigating away from a video that might be playing
        remove_video_players();
        const $media_list = $(this).parent();
        let $original_media_element;
        const is_video = $(this).hasClass("lightbox_video");
        // Because multiple media elements may match on the same data-url,
        // we capture the first of these
        if (is_video) {
            $original_media_element = $<HTMLMediaElement>(
                `.message_row a[href='${CSS.escape($(this).attr("data-url")!)}'] video`,
            )?.first();
        } else {
            $original_media_element = $<HTMLImageElement>(
                `.message_row a[href='${CSS.escape($(this).attr("data-url")!)}'] img`,
            )?.first();
        }

        // If $original_media_element comes with a 0 length, that means that
        // something in the message list has changed (e.g., a moved or
        // deleted message, or the deletion of a media element that was
        // available when the lightbox opened). In that event, we continue
        // to display whatever media is up in the lightbox, and remove
        // the thumbnail from the media list.
        if ($original_media_element.length === 0) {
            $(this).remove();
            return;
        }

        // Because a user could conceivably copy and paste a media reference
        // from another message, and because we are selecting the original
        // element above based on a data-url value that is therefore not
        // guaranteed to be unique, we pass the first (possibly only) media
        // element returned. The logic below for removing and adding the
        // "selected" class ensures that the correct thumbnail will
        // still be highlighted.
        open_image($original_media_element);

        if (!$(".image-list .image.selected").hasClass("lightbox_video") || !is_video) {
            pan_zoom_control.reset();
        }

        $(".image-list .image.selected").removeClass("selected");
        $(this).addClass("selected");

        const parentOffset = this.parentElement!.clientWidth + this.parentElement!.scrollLeft;
        // this is the left and right of the image compared to its parent.
        const coords = {
            left: this.offsetLeft,
            right: this.offsetLeft + this.clientWidth,
        };

        if (coords.right > parentOffset) {
            // add 2px margin
            $media_list.animate(
                {
                    scrollLeft: coords.right - this.parentElement!.clientWidth + 2,
                },
                100,
            );
        } else if (coords.left < this.parentElement!.scrollLeft) {
            // subtract 2px margin
            $media_list.animate({scrollLeft: coords.left - 2}, 100);
        }
    });

    $("#lightbox_overlay").on("click", ".center .arrow", function () {
        const direction = $(this).attr("data-direction");

        if (direction === "next") {
            next();
        } else if (direction === "prev") {
            prev();
        }
    });

    $("#lightbox_overlay").on("click", ".lightbox-zoom-reset", () => {
        if (!$("#lightbox_overlay .lightbox-zoom-reset").hasClass("disabled")) {
            pan_zoom_control.reset();
        }
    });

    $("#lightbox_overlay .player-container").on("click", function () {
        if ($(this).is(".player-container")) {
            reset_lightbox_state();
            overlays.close_active();
        }
    });

    $("#lightbox_overlay").on("click", ".media-info-wrapper, .center", (e) => {
        if ($(e.target).is(".media-info-wrapper, .center")) {
            reset_lightbox_state();
            overlays.close_overlay("lightbox");
        }
    });

    $("#lightbox_overlay .image-preview").on("click", (e) => {
        // Ensure that the click isn't on the image itself, and that
        // the window isn't marked as disabled to click to close.
        if (!$(e.target).is("img") && !$("#lightbox_overlay").data("noclose")) {
            reset_lightbox_state();
            overlays.close_overlay("lightbox");
        }
    });

    $("#lightbox_overlay .video-player").on("click", (e) => {
        // Close lightbox when clicked outside video.
        if (!$(e.target).is("video")) {
            overlays.close_overlay("lightbox");
        }
    });
}
