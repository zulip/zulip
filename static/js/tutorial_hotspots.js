var tutorial_hotspots = (function () {

var exports = {};

function restart_tutorial() {
    channel.post({
        url:      '/json/users/me/tutorial',
        data:     {},
        success:  function () {
        },
    });
}

function hotspot_success_function(data) {
    $(".tutorial-buttons").hide();
    for (var i = 0; i < data.next_pieces.length; i += 1) {
        $("#tutorial_hotspot_".concat(data.next_pieces[i])).show();
    }
}

function update_tutorial_status(update) {
    channel.patch({
        url:      '/json/users/me/tutorial',
        data:     {update_dict: JSON.stringify(update)},
        success:  function (data) {
            hotspot_success_function(data);
        },
    });
}

$(function () {
    $("#tutorial_hotspot_welcome").expectOne().click(function () {
        update_tutorial_status({welcome: true});
    });
    $("#tutorial_hotspot_streams").expectOne().click(function () {
        update_tutorial_status({streams: true});
    });
    $("#tutorial_hotspot_topics").expectOne().click(function () {
        update_tutorial_status({topics: true});
    });
    $("#tutorial_hotspot_narrowing").expectOne().click(function () {
        update_tutorial_status({narrowing: true});
    });
    $("#tutorial_hotspot_replying").expectOne().click(function () {
        update_tutorial_status({replying: true});
    });
    $("#tutorial_hotspot_get_started").expectOne().click(function () {
        update_tutorial_status({get_started: true});
    });
});

exports.initialize = function () {
    // for testing/demoing purposes - restarts the tutorial on refresh
    restart_tutorial();
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = tutorial_hotspots;
}
