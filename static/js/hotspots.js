var hotspots = (function () {

var exports = {};

exports.show = function (hotspot_list) {
    $('.hotspot').hide();
    for (var i = 0; i < hotspot_list.length; i += 1) {
        $("#hotspot_".concat(hotspot_list[i])).show();
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
    $("#hotspot_welcome").on('click', function (e) {
        mark_hotspot_as_read("welcome");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_streams").on('click', function (e) {
        mark_hotspot_as_read("streams");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_topics").on('click', function (e) {
        mark_hotspot_as_read("topics");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_narrowing").on('click', function (e) {
        mark_hotspot_as_read("narrowing");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_replying").on('click', function (e) {
        mark_hotspot_as_read("replying");
        e.preventDefault();
        e.stopPropagation();
    });
    $("#hotspot_get_started").on('click', function (e) {
        mark_hotspot_as_read("get_started");
        e.preventDefault();
        e.stopPropagation();
    });
});

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = hotspots;
}
