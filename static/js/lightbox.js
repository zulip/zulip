var lightbox = (function () {
var exports = {};

var is_open = false;
// the asset map is a map of all retrieved images and YouTube videos that are
// memoized instead of being looked up multiple times.
var asset_map = {

};

function render_lightbox_list_images(preview_source) {
    if (!is_open) {
        var images = Array.prototype.slice.call($(".focused_table .message_inline_image img"));
        var $image_list = $("#lightbox_overlay .image-list").html("");

        images.forEach(function (img) {
            var src = img.getAttribute("src");
            var className = preview_source === src ? "image selected" : "image";

            var node = $("<div></div>", {
                class: className,
                "data-src": src,
            }).css({ backgroundImage: "url(" + src + ")"});

            $image_list.append(node);
        }, "");
    }
}

function display_image(payload, options) {
    render_lightbox_list_images(payload.preview);

    $(".player-container").hide();
    $(".image-actions, .image-description, .download, .lightbox-canvas-trigger").show();

    if (options.lightbox_canvas === true) {
        var canvas = document.createElement("canvas");
        canvas.setAttribute("data-src", payload.source);

        $("#lightbox_overlay .image-preview").html(canvas).show();
        var photo = new LightboxCanvas(canvas);
        photo.speed(2.3);
    } else {
        var img = new Image();
        img.src = payload.source;

        $("#lightbox_overlay .image-preview").html(img).show();
    }

    $(".image-description .title").text(payload.title || "N/A");
    $(".image-description .user").text(payload.user);

    $(".image-actions .open, .image-actions .download").attr("href", payload.source);
}

function display_video(payload) {
    render_lightbox_list_images(payload.preview);

    $("#lightbox_overlay .image-preview, .image-description, .download, .lightbox-canvas-trigger").hide();

    var source;
    if (payload.type === "youtube-video") {
        source = "https://www.youtube.com/embed/" + payload.source;
    } else if (payload.type === "vimeo-video") {
        source = "https://player.vimeo.com/video/" + payload.source;
    }

    var iframe = $("<iframe></iframe>", {
        src: source,
        frameborder: 0,
        allowfullscreen: true,
    });

    $("#lightbox_overlay .player-container").html(iframe).show();

    var url = (payload.type === "youtube-video" ? "https://youtu.be/" : "https://vimeo.com/") + payload.source;
    $(".image-actions .open").attr("href", url);
}

// the image param is optional, but required on the first preview of an image.
// this will likely be passed in every time but just ignored if the result is already
// stored in the `asset_map`.
exports.open = function (image, options) {
    if (!options) {
        options = {
            // default to showing standard images.
            lightbox_canvas: $(".lightbox-canvas-trigger").hasClass("enabled"),
        };
    }

    var $image = $(image);

    // if wrapped in the .youtube-video class, it will be length = 1, and therefore
    // cast to true.
    var is_youtube_video = !!$image.closest(".youtube-video").length;
    var is_vimeo_video = !!$image.closest(".vimeo-video").length;

    // check if image is descendent of #preview_content
    var is_compose_preview_image = $image.closest("#preview_content").length === 1;
    var payload;
    // if the asset_map already contains the metadata required to display the
    // asset, just recall that metadata.
    var $image_source = $image.attr("data-src-fullsize") || $image.attr("src");
    if (asset_map[$image_source]) {
        payload = asset_map[$image_source];
    // otherwise retrieve the metadata from the DOM and store into the asset_map.
    } else {
        var $parent = $image.parent();
        var $type;
        var $source;
        if (is_youtube_video) {
            $type = "youtube-video";
            $source = $parent.attr("data-id");
        } else if (is_vimeo_video) {
            $type = "vimeo-video";
            $source = $parent.attr("data-id");
        } else {
            $type = "image";
            // thumbor supplies the src as thumbnail, data-src-fullsize as full-sized.
            if ($image.attr("data-src-fullsize")) {
                $source = $image.attr("data-src-fullsize");
            } else {
                $source = $image.attr("src");
            }
        }
        var sender_full_name;
        if (is_compose_preview_image) {
            sender_full_name = people.my_full_name();
        } else {
            var $message = $parent.closest("[zid]");
            var message = message_store.get($message.attr("zid"));
            if (message === undefined) {
                blueslip.error("Lightbox for unknown message " + $message.attr("zid"));
            }
            sender_full_name = message.sender_full_name;
        }
        payload = {
            user: sender_full_name,
            title: $parent.attr("title"),
            type: $type,
            preview: $image.attr("src"),
            source: $source,
        };

        asset_map[$source] = payload;
    }

    if (payload.type.match("-video")) {
        display_video(payload);
    } else if (payload.type === "image") {
        display_image(payload, options);
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
        name: 'lightbox',
        overlay: $("#lightbox_overlay"),
        on_close: lightbox_close_overlay,
    });

    popovers.hide_all();
    is_open = true;
};

exports.show_from_selected_message = function () {
    var $message_selected = $(".selected_message");
    var $message = $message_selected;
    var $image = $message.find(".message_inline_image img");
    var $prev_traverse = false;

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

exports.prev = function () {
    $(".image-list .image.selected").prev().click();
};

exports.next = function () {
    $(".image-list .image.selected").next().click();
};

// this is a block of events that are required for the lightbox to work.
exports.initialize = function () {
    $("#main_div, #preview_content").on("click", ".message_inline_image a", function (e) {
        // prevent the link from opening in a new page.
        e.preventDefault();
        // prevent the message compose dialog from happening.
        e.stopPropagation();
        var $img = $(this).find("img");
        exports.open($img);
    });

    $("#lightbox_overlay .download").click(function () {
        this.blur();
    });

    $("#lightbox_overlay").on("click", ".image-list .image", function () {
        var $image_list = $(this).parent();
        var original_image = $(".message_row img[src='" + $(this).attr('data-src') + "']");

        exports.open(original_image);

        $(".image-list .image.selected").removeClass("selected");
        $(this).addClass("selected");

        var parentOffset = this.parentNode.clientWidth + this.parentNode.scrollLeft;
        // this is the left and right of the image compared to its parent.
        var coords = {
            left: this.offsetLeft,
            right: this.offsetLeft + this.clientWidth,
        };

        if (coords.right > parentOffset) {
            // add 2px margin
            $image_list.animate({
                scrollLeft: coords.right - this.parentNode.clientWidth + 2,
            }, 100);
        } else if (coords.left < this.parentNode.scrollLeft) {
            // subtract 2px margin
            $image_list.animate({ scrollLeft: coords.left - 2 }, 100);
        }
    });

    $("#lightbox_overlay").on("click", ".center .arrow", function () {
        var direction = $(this).attr("data-direction");

        if (/^(next|prev)$/.test(direction)) {
            lightbox[direction]();
        }
    });

    $("#lightbox_overlay").on("click", ".lightbox-canvas-trigger", function () {
        var $img = $("#lightbox_overlay").find(".image-preview img");

        if ($img.length) {
            $(this).addClass("enabled");
            // the `lightbox.open` function will see the enabled class and
            // enable the `LightboxCanvas` class.
            exports.open($img);
        } else {
            $img = $("#lightbox_overlay").find(".image-preview canvas")[0].image;

            $(this).removeClass("enabled");
            exports.open($img);
        }
    });

    $("#lightbox_overlay .image-preview").on("dblclick", "img, canvas", function (e) {
        $("#lightbox_overlay .lightbox-canvas-trigger").click();
        e.preventDefault();
    });

    $("#lightbox_overlay .player-container").on("click", function () {
        if ($(this).is(".player-container")) {
            overlays.close_active();
        }
    });

    $("#lightbox_overlay").on("click", ".image-info-wrapper, .center", function (e) {
        if ($(e.target).is(".image-info-wrapper, .center")) {
            overlays.close_overlay("lightbox");
        }
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = lightbox;
}
window.lightbox = lightbox;
