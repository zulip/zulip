var lightbox = (function () {
var exports = {};

function display_image(image, user) {
    // image should be an Image Object in JavaScript.
    var url = $(image).attr("src");
    var title = $(image).parent().attr("title");

    $("#overlay .player-container").hide();
    $("#overlay .image-actions, .image-description, .download").show();

    var img = new Image();
    img.src = url;
    $("#overlay .image-preview").html("").show()
        .append(img);

    $(".image-description .title").text(title || "N/A");
    $(".image-description .user").text(user);

    $(".image-actions .open, .image-actions .download").attr("href", url);
}

function display_youtube_video(id) {
    $("#overlay .image-preview, .image-description, .download").hide();

    var iframe = document.createElement("iframe");
    iframe.width = window.innerWidth;
    iframe.height = window.innerWidth * 0.5625;
    iframe.src = "https://www.youtube.com/embed/" + id;
    iframe.setAttribute("frameborder", 0);
    iframe.setAttribute("allowfullscreen", true);

    $("#overlay .player-container").html("").show().append(iframe);
    $(".image-actions .open").attr("href", "https://youtu.be/" + id);
}

exports.open = function (data) {
    switch (data.type) {
        case "photo":
            display_image(data.image, data.user);
            break;
        case "youtube":
            display_youtube_video(data.id);
            break;
        default:
            break;
    }

    $("#overlay").addClass("show");
    popovers.hide_all();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = lightbox;
}
