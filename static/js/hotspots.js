var hotspots = (function () {

var exports = {};

exports.show = function (hotspot_list) {
    $('.hotspot').hide();
    for (var i = 0; i < hotspot_list.length; i += 1) {
        $("#hotspot_".concat(hotspot_list[i].name)).show();
    }
};

exports.initialize = function () {
    exports.show(page_params.hotspots);
};

function mark_hotspot_as_read(hotspot) {
    channel.post({
        url: '/json/users/me/hotspots',
        data: {hotspot: JSON.stringify(hotspot)},
    });
}

$(function () {
    $("#hotspot_click_to_reply").on('click', function (e) {
        mark_hotspot_as_read("click_to_reply");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_new_topic_button").on('click', function (e) {
        mark_hotspot_as_read("new_topic_button");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_stream_settings").on('click', function (e) {
        mark_hotspot_as_read("stream_settings");
        e.preventDefault();
        e.stopPropagation();
    });
});

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = hotspots;
}
