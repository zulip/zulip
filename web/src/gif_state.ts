import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import {realm} from "./state_data.ts";

type GifRating = "pg" | "pg-13" | "r" | "g";

export function is_tenor_enabled(): boolean {
    return (
        realm.tenor_api_key !== "" &&
        realm.realm_giphy_rating !== realm.gif_rating_options.disabled.id
    );
}

export function is_giphy_enabled(): boolean {
    return (
        realm.giphy_api_key !== "" &&
        realm.realm_giphy_rating !== realm.gif_rating_options.disabled.id
    );
}

export function get_rating(): GifRating {
    const options = realm.gif_rating_options;
    for (const rating of ["pg", "g", "pg-13", "r"] as const) {
        if (options[rating]?.id === realm.realm_giphy_rating) {
            return rating;
        }
    }

    // The below should never run unless a server bug allowed a
    // `gif_rating` value not present in `gif_rating_options`.
    blueslip.error("Invalid gif_rating value: " + realm.realm_giphy_rating);
    return "g";
}

export function update_gif_rating(): void {
    // Updating the GIF ratings would only result in us showing/hiding
    // the currently set GIF icon.
    // It won't change the GIF provider without a server restart as of now.
    if (realm.realm_giphy_rating === realm.gif_rating_options.disabled.id) {
        $(".zulip-icon-gif").hide();
    } else {
        $(".zulip-icon-gif").show();
    }
}
