"use strict";

const people = require("./people");

let is_open = false;
// the asset map is a map of all retrieved images and YouTube videos that are
// memoized instead of being looked up multiple times.
const asset_map = new Map();

function render_lightbox_list_images(preview_source) {
    if (!is_open) {
        const images = Array.prototype.slice.call($(".focused_table .message_inline_image img"));
        const $image_list = $("#lightbox_overlay .image-list").html("");

        images.forEach((img) => {
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
            exports.parse_image_data(img);
        }, "");
    }
}

function display_image(payload) {
    render_lightbox_list_images(payload.preview);

    $(".player-container").hide();
    $(".image-actions, .image-description, .download, .lightbox-canvas-trigger").show();

    const lightbox_canvas = $(".lightbox-canvas-trigger").hasClass("enabled");

    if (lightbox_canvas === true) {
        const canvas = document.createElement("canvas");
        canvas.setAttribute("data-src", payload.source);

        $("#lightbox_overlay .image-preview").html(canvas).show();
        const photo = new LightboxCanvas(canvas);
        photo.speed(2.3);
    } else {
        const img = new Image();
        img.src = payload.source;

        $("#lightbox_overlay .image-preview").html(img).show();
    }

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
    if (payload.type === "youtube-video") {
        source = "https://www.youtube.com/embed/" + payload.source;
    } else if (payload.type === "vimeo-video") {
        source = "https://player.vimeo.com/video/" + payload.source;
    } else if (payload.type === "embed-video") {
        // Use data: to load the player in a unique origin for security.
        source =
            "data:text/html," +
            window.encodeURIComponent(
                "<!DOCTYPE html><style>iframe{position:absolute;left:0;top:0;width:100%;height:100%;box-sizing:border-box}</style>" +
                    payload.source,
            );
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

exports.open = function ($image) {
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
            payload = exports.parse_image_data($image);
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

    function lightbox_close_overlay() {
        $(".player-container iframe").remove();
        is_open = false;
        document.activeElement.blur();
    }

    overlays.open_overlay({
        name: "lightbox",
        overlay: $("#lightbox_overlay"),
        on_close: lightbox_close_overlay,
    });

    popovers.hide_all();
    is_open = true;
};

exports.show_from_selected_message = function () {
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
        exports.open($image);
    }
};

// retrieve the metadata from the DOM and store into the asset_map.
exports.parse_image_data = function (image) {
    const $image = $(image);
    const $preview_src = $image.attr("src");

    if (asset_map.has($preview_src)) {
        // check if image's data is already present in asset_map.
        return;
    }

    // if wrapped in the .youtube-video class, it will be length = 1, and therefore
    // cast to true.
    const is_youtube_video = !!$image.closest(".youtube-video").length;
    const is_vimeo_video = !!$image.closest(".vimeo-video").length;
    const is_embed_video = !!$image.closest(".embed-video").length;

    // check if image is descendent of #preview_content
    const is_compose_preview_image = $image.closest("#preview_content").length === 1;

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
        // thumbor supplies the src as thumbnail, data-src-fullsize as full-sized.
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
};

exports.prev = function () {
    $(".image-list .image.selected").prev().trigger("click");
};

exports.next = function () {
    $(".image-list .image.selected").next().trigger("click");
};

// this is a block of events that are required for the lightbox to work.
exports.initialize = function () {
    $("#main_div, #preview_content").on("click", ".message_inline_image a", function (e) {
        // prevent the link from opening in a new page.
        e.preventDefault();
        // prevent the message compose dialog from happening.
        e.stopPropagation();
        const $img = $(this).find("img");
        exports.open($img);
    });

    $("#lightbox_overlay .download").on("click", function () {
        this.blur();
    });

    $("#lightbox_overlay").on("click", ".image-list .image", function () {
        const $image_list = $(this).parent();
        const $original_image = $(".message_row img[src='" + $(this).attr("data-src") + "']");

        exports.open($original_image);

        $(".image-list .image.selected").removeClass("selected");
        $(this).addClass("selected");

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
            exports.next();
        } else if (direction === "prev") {
            exports.prev();
        }
    });

    $("#lightbox_overlay").on("click", ".lightbox-canvas-trigger", function () {
        let $img = $("#lightbox_overlay").find(".image-preview img");

        if ($img.length) {
            $(this).addClass("enabled");
            // the `lightbox.open` function will see the enabled class and
            // enable the `LightboxCanvas` class.
            exports.open($img);
        } else {
            $img = $($("#lightbox_overlay").find(".image-preview canvas")[0].image);

            $(this).removeClass("enabled");
            exports.open($img);
        }
    });

    $("#lightbox_overlay .image-preview").on("dblclick", "img, canvas", (e) => {
        $("#lightbox_overlay .lightbox-canvas-trigger").trigger("click");
        e.preventDefault();
    });

    $("#lightbox_overlay .player-container").on("click", function () {
        if ($(this).is(".player-container")) {
            overlays.close_active();
        }
    });

    $("#lightbox_overlay").on("click", ".image-info-wrapper, .center", (e) => {
        if ($(e.target).is(".image-info-wrapper, .center")) {
            overlays.close_overlay("lightbox");
        }
    });
};

window.lightbox = exports;
