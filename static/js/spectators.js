// Module for displaying the modal asking spectators to login when
// attempting to do things that are not possible as a specatator (like
// add an emoji reaction, star a message, etc.).  While in many cases,
// we will prefer to hide menu options that don't make sense for
// spectators, this modal is useful for everything that doesn't make
// sense to remove from a design perspective.

import $ from "jquery";

import render_login_to_access_modal from "../templates/login_to_access.hbs";

import * as hash_util from "./hash_util";
import {page_params} from "./page_params";

export function login_to_access() {
    // Hide all overlays, popover and go back to the previous hash if the
    // hash has changed.
    let login_link;
    if (page_params.development_environment) {
        login_link = "/devlogin/?" + hash_util.current_hash_as_next();
    } else {
        login_link = "/login/?" + hash_util.current_hash_as_next();
    }

    $("#login-to-access-modal-holder").html(
        render_login_to_access_modal({
            signup_link: "/register",
            login_link,
        }),
    );
    $("#login_to_access_modal").modal("show");
}
