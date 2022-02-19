import panzoom from "@panzoom/panzoom";
import $ from "jquery";

import render_lightbox_overlay from "../templates/lightbox_overlay.hbs";

import * as blueslip from "./blueslip";
import * as message_store from "./message_store";
import * as overlays from "./overlays";
import * as people from "./people";
import * as popovers from "./popovers";
import * as rows from "./rows";

let is_open = false;
// the asset map is a map of all retrieved images and YouTube videos that are
// memoized instead of being looked up multiple times.
const asset_map = new Map();

export class PanZoomControl {
    // Class for both initializing and controlling the
    // the pan/zoom functionality.
    constructor(container) {
        this.container = container;
        this.panzoom = panzoom(this.container, {
            disablePan: true,
            disableZoom: true,
            cursor: "auto",
        });

        // The following events are necessary to prevent the click event
        // firing where the user "unclicks" at the end of the drag, which
        // was causing accidental overlay closes in some situations.
        this.container.addEventListener("panzoomstart", () => {
            // Marks this overlay as needing to stay open.
            $("#lightbox_overlay").data("noclose", true);
        });

        this.container.addEventListener("panzoomend", () => {
            // Don't remove the noclose attribute on this overlay until after paint,
            // otherwise it will be removed too early and close the lightbox
            // unintentionally.
            setTimeout(() => {
                $("#lightbox_overlay").data("noclose", false);
            }, 0);
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

    reset() {
        this.panzoom.reset();
    }

    disablePanZoom() {
        this.container.removeEventListener("wheel", this.panzoom.zoomWithWheel);
        this.panzoom.setOptions({disableZoom: true, disablePan: true, cursor: "auto"});
        this.reset();
    }

    enablePanZoom() {
        this.panzoom.setOptions({disableZoom: false, disablePan: false, cursor: "move"});
        this.container.addEventListener("wheel", this.panzoom.zoomWithWheel);
    }

    zoomIn() {
        this.panzoom.zoomIn();
    }

    zoomOut() {
        this.panzoom.zoomOut();
    }
}

export function clear_for_testing() {
    is_open = false;
    asset_map.clear();
}

export function render_lightbox_list_images(preview_source) {
    if (!is_open) {
        const images = Array.prototype.slice.call($(".focused_table .message_inline_image img"));
        const $image_list = $("#lightbox_overlay .image-list").html("");

        for (const img of images) {
            const src = img.getAttribute("src");
            const className = preview_source === src ? "image selected" : "image";

            const node = $("<div></div>", {
                class: className,
                "data-src": src,
            }).css({backgroundImage: "url(" + src + ")"});

            $image_list.append(node);

            // We parse the data for each image to show in the list,
            // while we still have its original DOM element handy, so
            // that navigating within the list only needs the `src`
            // attribute used to construct the node object above.
            parse_image_data(img);
        }
    }
}

function display_image(payload) {
    render_lightbox_list_images(payload.preview);

    $(".player-container").hide();
    $(".image-actions, .image-description, .download, .lightbox-canvas-trigger").show();

    const img_container = $("#lightbox_overlay .image-preview > .zoom-element");
    const img = new Image();
    img.src = payload.source;
    img_container.html(img).show();

    $(".image-description .title").text(payload.title || "N/A");
    $(".image-description .user").text(payload.user);

    $(".image-actions .open, .image-actions .download").attr("href", payload.source);
}

function display_video(payload) {
    render_lightbox_list_images(payload.preview);

    $(
        "#lightbox_overlay .image-preview, .image-description, .download, .lightbox-canvas-trigger",
    ).hide();

    let source;
    switch (payload.type) {
        case "youtube-video":
            source = "https://www.youtube.com/embed/" + payload.source;
            break;
        case "vimeo-video":
            source = "https://player.vimeo.com/video/" + payload.source;
            break;
        case "embed-video":
            // Use data: to load the player in a unique origin for security.
            source =
                "data:text/html," +
                window.encodeURIComponent(
                    "<!DOCTYPE html><style>iframe{position:absolute;left:0;top:0;width:100%;height:100%;box-sizing:border-box}</style>" +
                        payload.source,
                );
            break;
    }

    const iframe = $("<iframe></iframe>");
    iframe.attr(
        "sandbox",
        "allow-forms allow-modals allow-orientation-lock allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-presentation allow-same-origin allow-scripts",
    );
    iframe.attr("src", source);
    iframe.attr("frameborder", 0);
    iframe.attr("allowfullscreen", true);

    $("#lightbox_overlay .player-container").html(iframe).show();
    $(".image-actions .open").attr("href", payload.url);
}

export function build_open_image_function(on_close) {
    if (on_close === undefined) {
        on_close = function () {
            $(".player-container iframe").remove();
            is_open = false;
            document.activeElement.blur();
        };
    }

    return function ($image) {
        // if the asset_map already contains the metadata required to display the
        // asset, just recall that metadata.
        let $preview_src = $image.attr("src");
        let payload = asset_map.get($preview_src);
        if (payload === undefined) {
            if ($preview_src.endsWith("&size=full")) {
                // while fetching an image for canvas, `src` attribute supplies
                // full-sized image instead of thumbnail, so we have to replace
                // `size=full` with `size=thumbnail`.
                //
                // TODO: This is a hack to work around the fact that for
                // the lightbox canvas, the `src` is the data-fullsize-src
                // for the image, not the original thumbnail used to open
                // the lightbox.  A better fix will be to check a
                // `data-thumbnail-src` attribute that we add to the
                // canvas elements.
                $preview_src = $preview_src.replace(/.{4}$/, "thumbnail");
                payload = asset_map.get($preview_src);
            }
            if (payload === undefined) {
                payload = parse_image_data($image);
            }
        }

        if (payload.type.match("-video")) {
            display_video(payload);
        } else if (payload.type === "image") {
            display_image(payload);
        }

        if (is_open) {
            return;
        }

        overlays.open_overlay({
            name: "lightbox",
            overlay: $("#lightbox_overlay"),
            on_close,
        });

        popovers.hide_all();
        is_open = true;
    };
}

export function show_from_selected_message() {
    const $message_selected = $(".selected_message");
    let $message = $message_selected;
    let $image = $message.find(".message_inline_image img");
    let $prev_traverse = false;

    while ($image.length === 0) {
        if ($message.prev().length === 0) {
            $message = $message.parent().prev();
            if ($message.length === 0) {
                $prev_traverse = true;
                $message = $message_selected;
                break;
            } else {
                $message = $message.find(".last_message");
                continue;
            }
        }
        $message = $message.prev();
        $image = $message.find(".message_inline_image img");
    }

    if ($prev_traverse) {
        while ($image.length === 0) {
            if ($message.next().length === 0) {
                $message = $message.parent().next();
                if ($message.length === 0) {
                    break;
                } else {
                    $message = $message.children().first();
                    continue;
                }
            }
            $message = $message.next();
            $image = $message.find(".message_inline_image img");
        }
    }

    if ($image.length !== 0) {
        const open_image = build_open_image_function();
        open_image($image);
    }
}

// retrieve the metadata from the DOM and store into the asset_map.
export function parse_image_data(image) {
    const $image = $(image);
    const $preview_src = $image.attr("src");

    if (asset_map.has($preview_src)) {
        // check if image's data is already present in asset_map.
        return asset_map.get($preview_src);
    }

    // if wrapped in the .youtube-video class, it will be length = 1, and therefore
    // cast to true.
    const is_youtube_video = Boolean($image.closest(".youtube-video").length);
    const is_vimeo_video = Boolean($image.closest(".vimeo-video").length);
    const is_embed_video = Boolean($image.closest(".embed-video").length);

    // check if image is descendent of #compose .preview_content
    const is_compose_preview_image = $image.closest("#compose .preview_content").length === 1;

    const $parent = $image.parent();
    let $type;
    let $source;
    const $url = $parent.attr("href");
    if (is_youtube_video) {
        $type = "youtube-video";
        $source = $parent.attr("data-id");
    } else if (is_vimeo_video) {
        $type = "vimeo-video";
        $source = $parent.attr("data-id");
    } else if (is_embed_video) {
        $type = "embed-video";
        $source = $parent.attr("data-id");
    } else {
        $type = "image";
        if ($image.attr("data-src-fullsize")) {
            $source = $image.attr("data-src-fullsize");
        } else {
            $source = $preview_src;
        }
    }
    let sender_full_name;
    if (is_compose_preview_image) {
        sender_full_name = people.my_full_name();
    } else {
        const $message = $parent.closest("[zid]");
        const zid = rows.id($message);
        const message = message_store.get(zid);
        if (message === undefined) {
            blueslip.error("Lightbox for unknown message " + zid);
        } else {
            sender_full_name = message.sender_full_name;
        }
    }
    const payload = {
        user: sender_full_name,
        title: $parent.attr("title"),
        type: $type,
        preview: $preview_src,
        source: $source,
        url: $url,
    };

    asset_map.set($preview_src, payload);
    return payload;
}

export function prev() {
    $(".image-list .image.selected").prev().trigger("click");
}

export function next() {
    $(".image-list .image.selected").next().trigger("click");
}

// this is a block of events that are required for the lightbox to work.
export function initialize() {
    // Renders the DOM for the lightbox.
    const rendered_lightbox_overlay = render_lightbox_overlay();
    $("body").append(rendered_lightbox_overlay);

    // Bind the pan/zoom control the newly created element.
    const pan_zoom_control = new PanZoomControl(
        $("#lightbox_overlay .image-preview > .zoom-element")[0],
    );

    const reset_lightbox_state = function () {
        $(".player-container iframe").remove();
        is_open = false;
        document.activeElement.blur();
        pan_zoom_control.disablePanZoom();
        $(".lightbox-canvas-trigger").removeClass("enabled");
    };

    const open_image = build_open_image_function(reset_lightbox_state);

    $("#main_div, #compose .preview_content").on("click", ".message_inline_image a", function (e) {
        // prevent the link from opening in a new page.
        e.preventDefault();
        // prevent the message compose dialog from happening.
        e.stopPropagation();
        const $img = $(this).find("img");
        open_image($img);
    });

    $("#lightbox_overlay .download").on("click", function () {
        this.blur();
    });

    $("#lightbox_overlay").on("click", ".image-list .image", function () {
        const $image_list = $(this).parent();
        const $original_image = $(
            `.message_row img[src='${CSS.escape($(this).attr("data-src"))}']`,
        );

        open_image($original_image);

        $(".image-list .image.selected").removeClass("selected");
        $(this).addClass("selected");
        pan_zoom_control.reset();

        const parentOffset = this.parentNode.clientWidth + this.parentNode.scrollLeft;
        // this is the left and right of the image compared to its parent.
        const coords = {
            left: this.offsetLeft,
            right: this.offsetLeft + this.clientWidth,
        };

        if (coords.right > parentOffset) {
            // add 2px margin
            $image_list.animate(
                {
                    scrollLeft: coords.right - this.parentNode.clientWidth + 2,
                },
                100,
            );
        } else if (coords.left < this.parentNode.scrollLeft) {
            // subtract 2px margin
            $image_list.animate({scrollLeft: coords.left - 2}, 100);
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

    $("#lightbox_overlay").on("click", ".lightbox-canvas-trigger", function () {
        const $img = $("#lightbox_overlay").find(".image-preview img");
        open_image($img);

        if ($(this).hasClass("enabled")) {
            pan_zoom_control.disablePanZoom();
            $(this).removeClass("enabled");
        } else {
            pan_zoom_control.enablePanZoom();
            $(this).addClass("enabled");
        }
    });

    $("#lightbox_overlay .image-preview").on("dblclick", "img, canvas", (e) => {
        $("#lightbox_overlay .lightbox-canvas-trigger").trigger("click");
        e.preventDefault();
    });

    $("#lightbox_overlay .player-container").on("click", function () {
        if ($(this).is(".player-container")) {
            reset_lightbox_state();
            overlays.close_active();
        }
    });

    $("#lightbox_overlay").on("click", ".image-info-wrapper, .center", (e) => {
        if ($(e.target).is(".image-info-wrapper, .center")) {
            reset_lightbox_state();
            overlays.close_overlay("lightbox");
        }
    });
}
