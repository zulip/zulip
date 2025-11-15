import {realm} from "./state_data.ts";

export function is_tenor_enabled(): boolean {
    return realm.tenor_api_key !== "" && realm.tenor_client_key !== "";
}
