import $ from "jquery";
import type {z} from "zod";

import render_onboarding_video_modal from "../templates/onboarding_video_modal.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
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

function show_onboarding_video(): void {
    if (ONE_TIME_NOTICES_TO_DISPLAY.has("onboarding_video")) {
        const html_body = render_onboarding_video_modal({
            video_src: "../../static/videos/onboarding-video.mp4",
        });
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Welcome to Zulip!"}),
            html_body,
            on_click() {
                post_onboarding_step_as_read("onboarding_video");
            },
            html_submit_button: $t_html({defaultMessage: "Skip video — I'm familiar with Zulip"}),
            html_exit_button: $t_html({defaultMessage: "Watch later"}),
            close_on_submit: true,
            id: "onboarding-video-modal",
            close_on_overlay_click: false,
            post_render() {
                $("#onboarding-video-wrapper video").on("play", () => {
                    // Remove the custom play button overlaying the video.
                    $("#onboarding-video-wrapper").addClass("hide-play-button");
                });
            },
        });
    }
}

export function initialize(
    params: StateData["onboarding_steps"],
    show_message_view: (raw_terms: NarrowTerm[], opts: {trigger: string}) => void,
): void {
    update_onboarding_steps_to_display(params.onboarding_steps);
    narrow_to_dm_with_welcome_bot_new_user(params.onboarding_steps, show_message_view);
    show_onboarding_video();
}
