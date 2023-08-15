// Module for displaying the modal asking spectators to log in when
// attempting to do things that are not possible as a spectator (like
// add an emoji reaction, star a message, etc.).  While in many cases,
// we will prefer to hide menu options that don't make sense for
// spectators, this modal is useful for everything that doesn't make
// sense to remove from a design perspective.

import $ from "jquery";

import render_login_to_access_modal from "../templates/login_to_access.hbs";

import * as browser_history from "./browser_history";
import * as hash_util from "./hash_util";
import * as overlays from "./overlays";
import {page_params} from "./page_params";

export function login_to_access(empty_narrow?: boolean): void {
    // Hide all overlays, popover and go back to the previous hash if the
    // hash has changed.
    const login_link = hash_util.build_login_link();
    const realm_name = page_params.realm_name;

    $("body").append(
        render_login_to_access_modal({
            signup_link: "/register/",
            login_link,
            empty_narrow,
            realm_name,
        }),
    );

    overlays.open_modal("login_to_access_modal", {
        autoremove: true,
        on_hide() {
            browser_history.return_to_web_public_hash();
        },
    });
}
