import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";

let filter_out_inactives = false;

export function set_filter_out_inactives() {
    if (
        page_params.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.automatic.code
    ) {
        filter_out_inactives = stream_data.num_subscribed_subs() >= 30;
    } else if (
        page_params.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.always.code
    ) {
        filter_out_inactives = true;
    } else {
        filter_out_inactives = false;
    }
}

// for testing:
export function is_filtering_inactives() {
    return filter_out_inactives;
}

export function is_active(sub) {
    if (!filter_out_inactives || sub.pin_to_top) {
        // If users don't want to filter inactive streams
        // to the bottom, we respect that setting and don't
        // treat any streams as dormant.
        //
        // Currently this setting is automatically determined
        // by the number of streams.  See the callers
        // to set_filter_out_inactives.
        return true;
    }
    return stream_topic_history.stream_has_topics(sub.stream_id) || sub.newly_subscribed;
}

export function initialize() {
    set_filter_out_inactives();
}
