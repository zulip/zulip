import $ from "jquery";
import type {z} from "zod";

import render_onboarding_video_modal from "../templates/onboarding_video_modal.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
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
                // Do nothing
            },
            html_submit_button: $t_html({defaultMessage: "Skip video — I'm familiar with Zulip"}),
            html_exit_button: $t_html({defaultMessage: "Watch later"}),
            close_on_submit: true,
            id: "onboarding-video-modal",
            close_on_overlay_click: false,
            post_render() {
                const $watch_later_button = $("#onboarding-video-modal .dialog_exit_button");
                // $watch_later_button.on("click", (e) => {
                //     e.preventDefault();
                //     // Schedule a message.
                //     console.log("Is this a good time to watch the Welcome to Zulip video?");
                // });

                const $skip_video_button = $("#onboarding-video-modal .dialog_submit_button");
                $skip_video_button
                    .removeClass("dialog_submit_button")
                    .addClass("dialog_exit_button");
                $skip_video_button.css({"margin-left": "12px"});

                const $video = $("#onboarding-video-wrapper video");
                $video.on("play", () => {
                    // Remove the custom play button overlaying the video.
                    $("#onboarding-video-wrapper").addClass("hide-play-button");
                    $skip_video_button.text($t({defaultMessage: "Skip the rest"}));
                });
                $video.on("ended", () => {
                    $skip_video_button.css("visibility", "hidden");
                    $watch_later_button.css("visibility", "hidden");
                });
            },
            on_hide() {
                post_onboarding_step_as_read("onboarding_video");
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
