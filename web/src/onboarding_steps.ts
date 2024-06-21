import type {z} from "zod";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import type {StateData, onboarding_step_schema} from "./state_data";

export type OnboardingStep = z.output<typeof onboarding_step_schema>;

export const ONE_TIME_NOTICES_TO_DISPLAY = new Set<string>();

export function post_onboarding_step_as_read(onboarding_step_name: string): void {
    void channel.post({
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

export function update_onboarding_steps_to_display(onboarding_steps: OnboardingStep[]): void {
    ONE_TIME_NOTICES_TO_DISPLAY.clear();

    for (const onboarding_step of onboarding_steps) {
        if (onboarding_step.type === "one_time_notice") {
            ONE_TIME_NOTICES_TO_DISPLAY.add(onboarding_step.name);
        }
    }
}

export function initialize(params: StateData["onboarding_steps"]): void {
    update_onboarding_steps_to_display(params.onboarding_steps);
}
