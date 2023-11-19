import $ from "jquery";

import * as channel from "./channel";
import * as compose_call from "./compose_call";
import {get_recipient_label} from "./compose_closed_ui";
import * as compose_ui from "./compose_ui";
import {$t, $t_html} from "./i18n";
import {page_params} from "./page_params";
import * as rows from "./rows";
import * as ui_report from "./ui_report";
import * as util from "./util";

export function update_audio_and_video_chat_button_display() {
    update_audio_chat_button_display();
    update_video_chat_button_display();
}

export function update_video_chat_button_display() {
    const show_video_chat_button = compose_call.compute_show_video_chat_button();
    $(".compose-control-buttons-container .video_link").toggle(show_video_chat_button);
    $(".message-edit-feature-group .video_link").toggle(show_video_chat_button);
}

export function update_audio_chat_button_display() {
    const show_audio_chat_button = compose_call.compute_show_audio_chat_button();
    $(".compose-control-buttons-container .audio_link").toggle(show_audio_chat_button);
    $(".message-edit-feature-group .audio_link").toggle(show_audio_chat_button);
}

function insert_video_call_url(url, target_textarea) {
    const link_text = $t({defaultMessage: "Join video call."});
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea, "block", 1);
}

function insert_audio_call_url(url, target_textarea) {
    const link_text = $t({defaultMessage: "Join voice call."});
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea, "block", 1);
}

export function generate_and_insert_audio_or_video_call_link($target_element, is_audio_call) {
    let $target_textarea;
    let edit_message_id;
    if ($target_element.parents(".message_edit_form").length === 1) {
        edit_message_id = rows.id($target_element.parents(".message_row"));
        $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
    }

    const available_providers = page_params.realm_available_video_chat_providers;

    if (
        available_providers.zoom &&
        page_params.realm_video_chat_provider === available_providers.zoom.id
    ) {
        compose_call.abort_video_callbacks(edit_message_id);
        const key = edit_message_id || "";

        const request = {
            is_video_call: !is_audio_call,
        };

        const make_zoom_call = () => {
            compose_call.video_call_xhrs.set(
                key,
                channel.post({
                    url: "/json/calls/zoom/create",
                    data: request,
                    success(res) {
                        compose_call.video_call_xhrs.delete(key);
                        if (is_audio_call) {
                            insert_audio_call_url(res.url, $target_textarea);
                        } else {
                            insert_video_call_url(res.url, $target_textarea);
                        }
                    },
                    error(xhr, status) {
                        compose_call.video_call_xhrs.delete(key);
                        if (
                            status === "error" &&
                            xhr.responseJSON &&
                            xhr.responseJSON.code === "INVALID_ZOOM_TOKEN"
                        ) {
                            page_params.has_zoom_token = false;
                        }
                        if (status !== "abort") {
                            ui_report.generic_embed_error(
                                $t_html({defaultMessage: "Failed to create video call."}),
                            );
                        }
                    },
                }),
            );
        };

        if (page_params.has_zoom_token) {
            make_zoom_call();
        } else {
            compose_call.zoom_token_callbacks.set(key, make_zoom_call);
            window.open(
                window.location.protocol + "//" + window.location.host + "/calls/zoom/register",
                "_blank",
                "width=800,height=500,noopener,noreferrer",
            );
        }
    } else if (
        available_providers.big_blue_button &&
        page_params.realm_video_chat_provider === available_providers.big_blue_button.id
    ) {
        if (is_audio_call) {
            // TODO: Add support for audio-only BigBlueButton calls here.
            return;
        }
        const meeting_name = get_recipient_label() + " meeting";
        channel.get({
            url: "/json/calls/bigbluebutton/create",
            data: {
                meeting_name,
            },
            success(response) {
                insert_video_call_url(response.url, $target_textarea);
            },
        });
    } else {
        // TODO: Use `new URL` to generate the URLs here.
        const video_call_id = util.random_int(100000000000000, 999999999999999);
        const video_call_link = compose_call.get_jitsi_server_url() + "/" + video_call_id;
        if (is_audio_call) {
            insert_audio_call_url(
                video_call_link + "#config.startWithVideoMuted=true",
                $target_textarea,
            );
        } else {
            /* Because Jitsi remembers what last call type you joined
               in browser local storage, we need to specify that video
               should not be muted in the video call case, or your
               next call will also join without video after joining an
               audio-only call.

               This has the annoying downside that it requires users
               who have a personal preference to disable video every
               time, but Jitsi's UI makes that very easy to do, and
               that inconvenience is probably less important than letting
               the person organizing a call specify their intended
               call type (video vs audio).
           */
            insert_video_call_url(
                video_call_link + "#config.startWithVideoMuted=false",
                $target_textarea,
            );
        }
    }
}
