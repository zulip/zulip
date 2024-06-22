import {realm} from "./state_data";

export function is_giphy_enabled(): boolean {
    return (
        realm.giphy_api_key !== "" &&
        realm.realm_giphy_rating !== realm.giphy_rating_options.disabled.id
    );
}
