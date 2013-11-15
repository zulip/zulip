var admin = (function () {

var exports = {};

function populate_users () {
    var tb = $("#admin_users_table");
    tb.empty();

    var humans = [];
    var bots = [];

    realm_people_dict.each(function (user) {
        if (user.is_bot) {
            bots.push(user);
        } else {
            humans.push(user);
        }
    });

    humans = _.sortBy(humans, 'full_name');
    bots = _.sortBy(bots, 'full_name');

    var users = humans.concat(bots);

    _.each(users, function (user) {
        tb.append(templates.render("admin_user_list", {user: user}));
    });
}

exports.setup_page = function () {
    populate_users();

    $("#admin_users_table").on("click", ".deactivate", function (e) {
        e.preventDefault();
        e.stopPropagation();

        $(".active_user_row").removeClass("active_user_row");

        // Go up the tree until we find the user row, then grab the email element
        $(e.target).closest(".user_row").addClass("active_user_row");

        var user_name = $(".active_user_row").find('.user_name').text();
        var email = $(".active_user_row").find('.email').text();

        $("#deactivation_modal .email").text(email);
        $("#deactivation_modal .user_name").text(user_name);
        $("#deactivation_modal").modal("show");
    });

    $("#do_deactivate_button").click(function (e) {
        if ($("#deactivation_modal .email").html() !== $(".active_user_row").find('.email').text()) {
            blueslip.error("User deactivation canceled due to non-matching fields.");
            ui.report_message("Deactivation encountered an error. Please reload and try again.",
               $("#home-error"), 'alert-error');
        }
        $("#deactivation_modal").modal("hide");
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
                $(".active_user_row button").removeClass("btn-danger").text("Deactivated");
                $(".active_user_row span").wrap("<strike>");
            }
        });
    });

};

return exports;

}());
