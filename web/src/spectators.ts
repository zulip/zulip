// Module for displaying the modal asking spectators to log in when
// attempting to do things that are not possible as a spectator (like
// add an emoji reaction, star a message, etc.).  While in many cases,
// we will prefer to hide menu options that don't make sense for
// spectators, this modal is useful for everything that doesn't make
// sense to remove from a design perspective.

import $ from "jquery";

import render_login_to_access_modal from "../templates/login_to_access.hbs";

import {page_params} from "./base_page_params";
import * as browser_history from "./browser_history";
import * as modals from "./modals";
import {realm} from "./state_data";

export function current_hash_as_next(): string {
    return `next=/${encodeURIComponent(window.location.hash)}`;
}

export function build_login_link(): string {
    let login_link = "/login/?" + current_hash_as_next();
    if (page_params.development_environment) {
        login_link = "/devlogin/?" + current_hash_as_next();
    }
    return login_link;
}

export function login_to_access(empty_narrow?: boolean): void {
    // Hide all overlays, popover and go back to the previous hash if the
    // hash has changed.
    const login_link = build_login_link();
    const realm_name = realm.realm_name;

    $("body").append(
        $(
            render_login_to_access_modal({
                signup_link: "/register/",
                login_link,
                empty_narrow,
                realm_name,
            }),
        ),
    );

    modals.open("login_to_access_modal", {
        autoremove: true,
        on_hide() {
            browser_history.return_to_web_public_hash();
        },
    });
}
