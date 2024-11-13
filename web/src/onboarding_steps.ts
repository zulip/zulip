import type {z} from "zod";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as people from "./people.ts";
import type {NarrowTerm, StateData, onboarding_step_schema} from "./state_data.ts";

export type OnboardingStep = z.output<typeof onboarding_step_schema>;

export const ONE_TIME_NOTICES_TO_DISPLAY = new Set<string>();

export function post_onboarding_step_as_read(onboarding_step_name: string): void {
    void channel.post({
        url: "/json/users/me/onboarding_steps",
        data: {onboarding_step: onboarding_step_name},
        error(err) {
            if (err.readyState !== 0) {
                blueslip.error(`Failed to mark ${onboarding_step_name} as read.`, {
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

function narrow_to_dm_with_welcome_bot_new_user(
    onboarding_steps: OnboardingStep[],
    show_message_view: (raw_terms: NarrowTerm[], opts: {trigger: string}) => void,
): void {
    if (
        onboarding_steps.some(
            (onboarding_step) => onboarding_step.name === "narrow_to_dm_with_welcome_bot_new_user",
        )
    ) {
        show_message_view(
            [
                {
                    operator: "dm",
                    operand: people.WELCOME_BOT.email,
                },
            ],
            {trigger: "sidebar"},
        );
        post_onboarding_step_as_read("narrow_to_dm_with_welcome_bot_new_user");
    }
}

export function initialize(
    params: StateData["onboarding_steps"],
    show_message_view: (raw_terms: NarrowTerm[], opts: {trigger: string}) => void,
): void {
    update_onboarding_steps_to_display(params.onboarding_steps);
    narrow_to_dm_with_welcome_bot_new_user(params.onboarding_steps, show_message_view);
}
