import {z} from "zod";

import * as blueslip from "./blueslip";
import * as channel from "./channel";

const one_time_notice_schema = z.object({
    name: z.string(),
    type: z.literal("one_time_notice"),
});

/* We may introduce onboarding step of types other than 'one time notice'
in future. Earlier, we had 'hotspot' and 'one time notice' as the two
types. We can simply do:
const onboarding_step_schema = z.union([one_time_notice_schema, other_type_schema]);
to avoid major refactoring when new type is introduced in the future. */
const onboarding_step_schema = one_time_notice_schema;

export type OnboardingStep = z.output<typeof onboarding_step_schema>;

export const ONE_TIME_NOTICES_TO_DISPLAY = new Set<string>();

export const post_onboarding_step_as_read = (onboarding_step_name: string): void => {
    void channel.post({
        url: "/json/users/me/onboarding_steps",
        data: {onboarding_step: onboarding_step_name},
        error: (err) => {
            if (err.readyState !== 0) {
                blueslip.error("Failed to fetch onboarding steps", {
                    readyState: err.readyState,
                    status: err.status,
                    body: err.responseText,
                });
            }
        },
    });
};

export const update_onboarding_steps_to_display = (onboarding_steps: OnboardingStep[]): void => {
    ONE_TIME_NOTICES_TO_DISPLAY.clear();

    for (const onboarding_step of onboarding_steps) {
        if (onboarding_step.type === "one_time_notice") {
            ONE_TIME_NOTICES_TO_DISPLAY.add(onboarding_step.name);
        }
    }
};

export const initialize = (params: {onboarding_steps: OnboardingStep[]}): void => {
    update_onboarding_steps_to_display(params.onboarding_steps);
};
