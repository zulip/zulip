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
            var className = preview_source.match(src) ? "image selected" : "image";

            var node = $("<div></div>", {
                class: className,
                "data-src": src,
            }).css({ backgroundImage: "url(" + src + ")"});

            $image_list.append(node);
        }, "");
    }
}

function display_image(payload) {
    render_lightbox_list_images(payload.preview);

    $(".player-container").hide();
    $(".image-actions, .image-description, .download").show();

    var img = new Image();
    img.src = payload.source;
    $("#lightbox_overlay .image-preview").html(img).show();

    $(".image-description .title").text(payload.title || "N/A");
    $(".image-description .user").text(payload.user);

    $(".image-actions .open, .image-actions .download").attr("href", payload.source);
}

function display_youtube_video(payload) {
    render_lightbox_list_images(payload.preview);

    $("#lightbox_overlay .image-preview, .image-description, .download").hide();

    var iframe = $("<iframe></iframe>", {
        src: "https://www.youtube.com/embed/" + payload.source,
        frameborder: 0,
        allowfullscreen: true,
    });

    $("#lightbox_overlay .player-container").html(iframe).show();
    $(".image-actions .open").attr("href", "https://youtu.be/" + payload.source);
}

// the image param is optional, but required on the first preview of an image.
// this will likely be passed in every time but just ignored if the result is already
// stored in the `asset_map`.
exports.open = function (image) {
    var $image = $(image);

    // if wrapped in the .youtube-video class, it will be length = 1, and therefore
    // cast to true.
    var is_youtube_video = !!$image.closest(".youtube-video").length;

    var payload;
    // if the asset_map already contains the metadata required to display the
    // asset, just recall that metadata.
    if (asset_map[$image.attr("src")]) {
        payload = asset_map[$image.attr("src")];

        if (payload.type === "youtube-video") {
            display_youtube_video(payload);
        } else if (payload.type === "image") {
            display_image(payload);
        }
    // otherwise retrieve the metadata from the DOM and store into the asset_map.
    } else {
        var $parent = $image.parent();
        var $message = $parent.closest("[zid]");

        payload = {
            user: message_store.get($message.attr("zid")).sender_full_name,
            title: $image.parent().attr("title"),
            type: is_youtube_video ? "youtube-video" : "image",
            preview: $image.attr("src"),
            source: is_youtube_video ? $parent.attr("data-id") : $image.attr("src"),
        };

        asset_map[payload.preview] = payload;

        if (payload.type === "youtube-video") {
            display_youtube_video(payload);
        } else if (payload.type === "image") {
            display_image(payload);
        }
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
    var $message = $(".selected_message");
    var $image = $message.find("img");

    while ($image.length === 0) {
        $message = $message.prev();
        if ($message.length === 0) {
            break;
        }
        $image = $message.find("img");
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
$(function () {
    $("#main_div").on("click", ".message_inline_image a", function (e) {
        var $img = $(this).find("img");

        // prevent the link from opening in a new page.
        e.preventDefault();
        // prevent the message compose dialog from happening.
        e.stopPropagation();

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

});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = lightbox;
}
