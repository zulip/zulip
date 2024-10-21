import $ from "jquery";
import assert from "minimalistic-assert";
import type {z} from "zod";

import render_onboarding_video_modal from "../templates/onboarding_video_modal.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as people from "./people.ts";
import type {NarrowTerm, StateData, onboarding_step_schema} from "./state_data.ts";
import {realm} from "./state_data.ts";
import * as util from "./util.ts";

export type OnboardingStep = z.output<typeof onboarding_step_schema>;

export const ONE_TIME_NOTICES_TO_DISPLAY = new Set<string>();

export function post_onboarding_step_as_read(
    onboarding_step_name: string,
    schedule_onboarding_video_reminder_delay?: number,
): void {
    const data: {onboarding_step: string; schedule_onboarding_video_reminder_delay?: number} = {
        onboarding_step: onboarding_step_name,
    };
    if (schedule_onboarding_video_reminder_delay !== undefined) {
        assert(onboarding_step_name === "onboarding_video");
        data.schedule_onboarding_video_reminder_delay = schedule_onboarding_video_reminder_delay;
    }
    void channel.post({
        url: "/json/users/me/onboarding_steps",
        data,
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
        const onboarding_video_url = realm.onboarding_video_url;
        assert(onboarding_video_url !== undefined);
        const html_body = render_onboarding_video_modal({
            video_src: onboarding_video_url,
        });
        let watch_later_clicked = false;
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
                $watch_later_button.on("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    // Schedule a reminder message.
                    const reminder_delay_seconds = 30;
                    post_onboarding_step_as_read("onboarding_video", reminder_delay_seconds);
                    watch_later_clicked = true;
                    dialog_widget.close();
                });

                const $skip_video_button = $("#onboarding-video-modal .dialog_submit_button");
                $skip_video_button
                    .removeClass("dialog_submit_button")
                    .addClass("dialog_exit_button");
                $skip_video_button.css({"margin-left": "12px"});

                const $video = $<HTMLVideoElement>("#onboarding-video-wrapper video");
                $video.on("play", () => {
                    // Remove the custom play button overlaying the video.
                    $("#onboarding-video-wrapper").addClass("hide-play-button");
                });

                let skip_video_button_text_updated = false;
                let video_ended_button_visible = false;
                $video.on("timeupdate", () => {
                    const $video_elem = util.the($video);
                    const current_time = $video_elem.currentTime;
                    if (!skip_video_button_text_updated && current_time >= 30) {
                        $skip_video_button.text($t({defaultMessage: "Skip the rest"}));
                        skip_video_button_text_updated = true;
                    }
                    if (video_ended_button_visible && current_time < $video_elem.duration) {
                        $("#video-ended-button-wrapper").css("visibility", "hidden");
                        video_ended_button_visible = false;
                    }
                });

                $video.on("ended", () => {
                    $("#video-ended-button-wrapper").css("visibility", "visible");
                    video_ended_button_visible = true;
                    $skip_video_button.css("visibility", "hidden");
                    $watch_later_button.css("visibility", "hidden");
                });

                $("#video-ended-button-wrapper > button").on("click", () => {
                    dialog_widget.close();
                });
            },
            on_hide() {
                if (!watch_later_clicked) {
                    // $watch_later_button click handler already calls this function.
                    post_onboarding_step_as_read("onboarding_video");
                }
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
