var admin = (function () {

var exports = {};

function failed_listing_users(xhr, error) {
    util.destroy_loading_indicator($('#subs_page_loading_indicator'));
    ui.report_error("Error listing users or bots", xhr, $("#administration-status"));
}

function failed_listing_streams(xhr, error) {
    ui.report_error("Error listing streams", xhr, $("#administration-status"));
}

function populate_users (realm_people_data) {
    var users_table = $("#admin_users_table");
    var deactivated_users_table = $("#admin_deactivated_users_table");
    var bots_table = $("#admin_bots_table");
    // Clear table rows, but not the table headers
    users_table.find("tr.user_row").remove();
    deactivated_users_table.find("tr.user_row").remove();
    bots_table.find("tr.user_row").remove();

    var active_users = [];
    var deactivated_users = [];
    var bots = [];
    _.each(realm_people_data.members, function (user) {
        if (user.is_bot) {
            bots.push(user);
        } else if (user.is_active) {
            active_users.push(user);
        } else {
            deactivated_users.push(user);
        }
    });

    active_users = _.sortBy(active_users, 'full_name');
    deactivated_users = _.sortBy(deactivated_users, 'full_name');
    bots = _.sortBy(bots, 'full_name');

    _.each(bots, function (user) {
        bots_table.append(templates.render("admin_user_list", {user: user}));
    });
    _.each(active_users, function (user) {
        users_table.append(templates.render("admin_user_list", {user: user}));
    });
    _.each(deactivated_users, function (user) {
        deactivated_users_table.append(templates.render("admin_user_list", {user: user}));
    });
    util.destroy_loading_indicator($('#admin_page_users_loading_indicator'));
    util.destroy_loading_indicator($('#admin_page_bots_loading_indicator'));
    util.destroy_loading_indicator($('#admin_page_deactivated_users_loading_indicator'));
}

function populate_streams (streams_data) {
    var streams_table = $("#admin_streams_table").expectOne();
    streams_table.find("tr.stream_row").remove();
    _.each(streams_data.streams, function (stream) {
        streams_table.append(templates.render("admin_streams_list", {stream: stream}));
    });
    util.destroy_loading_indicator($('#admin_page_streams_loading_indicator'));
}

exports.setup_page = function () {
    // create loading indicators
    util.make_loading_indicator($('#admin_page_users_loading_indicator'));
    util.make_loading_indicator($('#admin_page_bots_loading_indicator'));
    util.make_loading_indicator($('#admin_page_streams_loading_indicator'));
    util.make_loading_indicator($('#admin_page_deactivated_users_loading_indicator'));

    // Populate users and bots tables
    $.ajax({
        type:     'GET',
        url:      '/json/users',
        dataType: 'json',
        timeout:  10*1000,
        success: populate_users,
        error: failed_listing_users
    });

    // Populate streams table
    $.ajax({
        type:     'POST',
        url:      '/json/get_public_streams',
        dataType: 'json',
        timeout:  10*1000,
        success: populate_streams,
        error: failed_listing_streams
    });

    // Setup click handlers
    $(".admin_user_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_user_row").removeClass("active_user_row");

        $(e.target).closest(".user_row").addClass("active_user_row");

        var user_name = $(".active_user_row").find('.user_name').text();
        var email = $(".active_user_row").find('.email').text();

        $("#deactivation_user_modal .email").text(email);
        $("#deactivation_user_modal .user_name").text(user_name);
        $("#deactivation_user_modal").modal("show");
    });

    $(".admin_stream_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_stream_row").removeClass("active_stream_row");

        $(e.target).closest(".stream_row").addClass("active_stream_row");

        var stream_name = $(".active_stream_row").find('.stream_name').text();

        $("#deactivation_stream_modal .stream_name").text(stream_name);
        $("#deactivation_stream_modal").modal("show");
    });

    $(".admin_user_table").on("click", ".reactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        $(e.target).closest(".user_row").addClass("active_user_row");

        var email = $(".active_user_row").find('.email').text();
        $.ajax({
            type: 'POST',
            url: '/json/users/' + $(".active_user_row").find('.email').text() + "/reactivate",
            error: function (xhr, error_type) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_user_row button").closest("td").html(
                        $("<p>").addClass("text-error").text($.parseJSON(xhr.responseText).msg)
                    );
                } else {
                     $(".active_user_row button").text("Failed!");
                }
            },
            success: function () {
                var row = $(".active_user_row");
                var button = $(".active_user_row button");
                button.addClass("btn-danger");
                button.removeClass("btn-warning");
                button.addClass("deactivate");
                button.removeClass("reactivate");
                button.text("Deactivate");
                row.removeClass("inactive_user_row");
            }
        });
    });

    $("#do_deactivate_user_button").click(function (e) {
        if ($("#deactivation_user_modal .email").html() !== $(".active_user_row").find('.email').text()) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui.report_message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_user_modal").modal("hide");
        $(".active_user_row button").prop("disabled", true).text("Working…");
        $.ajax({
            type: 'DELETE',
            url: '/json/users/' + $(".active_user_row").find('.email').text(),
            error: function (xhr, error_type) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_user_row button").closest("td").html(
                        $("<p>").addClass("text-error").text($.parseJSON(xhr.responseText).msg)
                    );
                } else {
                     $(".active_user_row button").text("Failed!");
                }
            },
            success: function () {
                var row = $(".active_user_row");
                var button = $(".active_user_row button");
                button.prop("disabled", false);
                button.addClass("btn-warning");
                button.removeClass("btn-danger");
                button.addClass("reactivate");
                button.removeClass("deactivate");
                button.text("Reactivate");
                row.addClass("inactive_user_row");
            }
        });
    });

    $("#do_deactivate_stream_button").click(function (e) {
        if ($("#deactivation_stream_modal .stream_name").text() !== $(".active_stream_row").find('.stream_name').text()) {
            blueslip.error("Stream deactivation canceled due to non-matching fields.");
            ui.report_message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_stream_modal").modal("hide");
        $(".active_stream_row button").prop("disabled", true).text("Working…");
        $.ajax({
            type: 'DELETE',
            url: '/json/streams/' + encodeURIComponent($(".active_stream_row").find('.stream_name').text()),
            error: function (xhr, error_type) {
                if (xhr.status.toString().charAt(0) === "4") {
                    $(".active_stream_row button").closest("td").html(
                        $("<p>").addClass("text-error").text($.parseJSON(xhr.responseText).msg)
                    );
                } else {
                     $(".active_stream_row button").text("Failed!");
                }
            },
            success: function () {
                var row = $(".active_stream_row");
                row.remove();
            }
        });
    });
};

return exports;

}());
