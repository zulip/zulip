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
    if (realm.realm_giphy_rating === realm.gif_rating_options.disabled.id) {
        $(".compose-gif-icon-giphy").hide();
        $(".compose-gif-icon-tenor").hide();
        return;
    }

    // We want to avoid showing the GIPHY icon in case Tenor is enabled.
    if (realm.giphy_api_key === "" || realm.tenor_api_key !== "") {
        $(".compose-gif-icon-giphy").hide();
    } else {
        $(".compose-gif-icon-giphy").show();
    }

    if (realm.tenor_api_key === "") {
        $(".compose-gif-icon-tenor").hide();
    } else {
        $(".compose-gif-icon-tenor").show();
    }
}
