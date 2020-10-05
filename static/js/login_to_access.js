"use strict";

const render_login_to_access_modal = require("../templates/login_to_access.hbs");

exports.show = function () {
    // Hide all overlays, popover and go back to the previous hash if the
    // hash has changed.
    $("#login-to-access-modal-holder").html(render_login_to_access_modal);
    $("#login_to_access_modal").modal("show");
};

window.login_to_access = exports;
