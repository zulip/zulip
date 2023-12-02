import * as blueslip from "./blueslip";
import * as channel from "./channel";

export function post_onboarding_step_as_read(onboarding_step_name) {
    channel.post({
        url: "/json/users/me/onboarding_steps",
        data: {onboarding_step: onboarding_step_name},
        error(err) {
            if (err.readyState !== 0) {
                blueslip.error("Failed to fetch onboarding steps", {
                    readyState: err.readyState,
                    status: err.status,
                    body: err.responseText,
                });
            }
        },
    });
}

export function filter_new_hotspots(onboarding_steps) {
    return onboarding_steps.filter((onboarding_step) => onboarding_step.type === "hotspot");
}
