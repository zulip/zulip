import $ from "jquery";
import {
    LocalAudioTrack,
    type LocalTrack,
    LocalVideoTrack,
    Room,
    createLocalAudioTrack,
    createLocalTracks,
    createLocalVideoTrack,
} from "livekit-client";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import {type PrejoinResult, update_toggle_button} from "./livekit_call_room.ts";

export type PrejoinOutcome = {
    prejoin: PrejoinResult;
    token: string;
};

const mint_token_response_schema = z.object({token: z.string()});

type MintResult = {token: string} | {error: string};

async function mint_livekit_token(call_payload: string): Promise<MintResult> {
    return new Promise((resolve) => {
        channel.post({
            url: "/json/calls/livekit/token",
            data: {call: call_payload},
            success(data: unknown) {
                const parsed = mint_token_response_schema.safeParse(data);
                if (parsed.success) {
                    resolve({token: parsed.data.token});
                } else {
                    resolve({
                        error: $t({
                            defaultMessage: "Could not prepare the call. Please try again.",
                        }),
                    });
                }
            },
            error(xhr: JQuery.jqXHR<unknown>) {
                const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
                resolve({
                    error: parsed.success
                        ? parsed.data.msg
                        : $t({
                              defaultMessage: "Could not prepare the call. Please try again.",
                          }),
                });
            },
        });
    });
}

type PrejoinState = {
    audio_track: LocalAudioTrack | null;
    video_track: LocalVideoTrack | null;
    mic_enabled: boolean;
    camera_enabled: boolean;
    speaker_device_id: string | null;
    detach_meter: (() => void) | null;
};

function get_track_device_id(track: LocalTrack): string | null {
    const settings = track.mediaStreamTrack.getSettings();
    return settings.deviceId ?? null;
}

async function acquire_tracks(is_video_call: boolean): Promise<{
    audio: LocalAudioTrack | null;
    video: LocalVideoTrack | null;
}> {
    if (is_video_call) {
        try {
            const tracks = await createLocalTracks({audio: true, video: true});
            let audio: LocalAudioTrack | null = null;
            let video: LocalVideoTrack | null = null;
            for (const track of tracks) {
                if (track instanceof LocalAudioTrack) {
                    audio = track;
                } else if (track instanceof LocalVideoTrack) {
                    video = track;
                }
            }
            return {audio, video};
        } catch {
            // Fall through and try independently so mic-only setups still work.
        }
    }
    let audio: LocalAudioTrack | null = null;
    try {
        audio = await createLocalAudioTrack();
    } catch {
        // Mic permission denied or no mic present.
    }
    let video: LocalVideoTrack | null = null;
    if (is_video_call) {
        try {
            video = await createLocalVideoTrack();
        } catch {
            // Camera permission denied or no camera present.
        }
    }
    return {audio, video};
}

function attach_mic_meter(track: LocalAudioTrack, bar: HTMLElement): () => void {
    const ctx = new AudioContext();
    const stream = new MediaStream([track.mediaStreamTrack]);
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    const buffer = new Uint8Array(analyser.fftSize);
    let raf = 0;
    let stopped = false;

    const tick = (): void => {
        if (stopped) {
            return;
        }
        analyser.getByteTimeDomainData(buffer);
        let sum = 0;
        for (const v of buffer) {
            const centered = v - 128;
            sum += centered * centered;
        }
        const rms = Math.sqrt(sum / buffer.length) / 128;
        // Multiplier boosts typical speech level to a readable range;
        // clamp to 1 for loud audio.
        const level = Math.min(1, rms * 2.5);
        bar.style.transform = `scaleX(${level})`;
        raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
        stopped = true;
        cancelAnimationFrame(raf);
        source.disconnect();
        analyser.disconnect();
        void ctx.close();
        bar.style.transform = "scaleX(0)";
    };
}

function populate_device_select(
    select: HTMLSelectElement,
    devices: MediaDeviceInfo[],
    current_device_id: string | null,
    fallback_label: (index: number) => string,
): void {
    const $select = $(select);
    $select.empty();
    for (const [index, device] of devices.entries()) {
        const $option = $("<option>")
            .val(device.deviceId)
            .text(device.label || fallback_label(index));
        if (device.deviceId === current_device_id) {
            $option.prop("selected", true);
        }
        $select.append($option);
    }
    $select.prop("disabled", devices.length === 0);
}

async function populate_all_devices(state: PrejoinState): Promise<void> {
    const [mics, cameras, speakers] = await Promise.all([
        Room.getLocalDevices("audioinput", false),
        Room.getLocalDevices("videoinput", false),
        Room.getLocalDevices("audiooutput", false),
    ]);
    const mic_select = document.querySelector<HTMLSelectElement>("#livekit-prejoin-mic-select")!;
    populate_device_select(
        mic_select,
        mics,
        state.audio_track === null ? null : get_track_device_id(state.audio_track),
        (i) => $t({defaultMessage: "Microphone {index}"}, {index: i + 1}),
    );
    const camera_select = document.querySelector<HTMLSelectElement>(
        "#livekit-prejoin-camera-select",
    )!;
    populate_device_select(
        camera_select,
        cameras,
        state.video_track === null ? null : get_track_device_id(state.video_track),
        (i) => $t({defaultMessage: "Camera {index}"}, {index: i + 1}),
    );

    if ("setSinkId" in HTMLMediaElement.prototype && speakers.length > 0) {
        $("#livekit-prejoin-speaker-row").prop("hidden", false);
        const speaker_select = document.querySelector<HTMLSelectElement>(
            "#livekit-prejoin-speaker-select",
        )!;
        populate_device_select(speaker_select, speakers, state.speaker_device_id, (i) =>
            $t({defaultMessage: "Speaker {index}"}, {index: i + 1}),
        );
    } else {
        $("#livekit-prejoin-speaker-row").prop("hidden", true);
    }
}

function apply_camera_visibility(state: PrejoinState): void {
    const has_video = state.video_track !== null && state.camera_enabled;
    $("#livekit-prejoin-video").prop("hidden", !has_video);
    $("#livekit-prejoin-video-off").prop("hidden", has_video);
}

function apply_mic_available(state: PrejoinState): void {
    if (state.audio_track === null) {
        $("#livekit-prejoin-toggle-mic").prop("disabled", true);
        update_toggle_button("livekit-prejoin-toggle-mic", false);
    }
}

function apply_camera_available(state: PrejoinState, is_video_call: boolean): void {
    const $button = $("#livekit-prejoin-toggle-camera");
    if (!is_video_call) {
        $button.prop("disabled", true);
        $button.prop("hidden", true);
        $("#livekit-prejoin-camera-row").prop("hidden", true);
        update_toggle_button("livekit-prejoin-toggle-camera", false);
        return;
    }
    if (state.video_track === null) {
        $button.prop("disabled", true);
        $("#livekit-prejoin-camera-row").prop("hidden", true);
        update_toggle_button("livekit-prejoin-toggle-camera", false);
    }
}

function set_error(message: string): void {
    const $el = $("#livekit-prejoin-error");
    $el.text(message);
    $el.prop("hidden", message === "");
}

async function switch_microphone(state: PrejoinState, device_id: string): Promise<void> {
    const track = state.audio_track;
    if (track === null) {
        return;
    }
    try {
        await track.restartTrack({deviceId: {exact: device_id}});
    } catch {
        set_error($t({defaultMessage: "Could not switch to the selected microphone."}));
        return;
    }
    if (state.detach_meter !== null) {
        state.detach_meter();
        state.detach_meter = attach_mic_meter(
            track,
            document.querySelector<HTMLElement>("#livekit-prejoin-meter-bar")!,
        );
    }
}

async function switch_camera(state: PrejoinState, device_id: string): Promise<void> {
    const track = state.video_track;
    if (track === null) {
        return;
    }
    try {
        await track.restartTrack({deviceId: {exact: device_id}});
    } catch {
        set_error($t({defaultMessage: "Could not switch to the selected camera."}));
    }
}

async function setup_prejoin_ui(state: PrejoinState, is_video_call: boolean): Promise<void> {
    $("#livekit-prejoin-status").text(
        $t({defaultMessage: "Requesting camera and microphone access…"}),
    );

    const {audio, video} = await acquire_tracks(is_video_call);
    state.audio_track = audio;
    state.video_track = video;
    if (audio === null) {
        state.mic_enabled = false;
    }
    if (video === null) {
        state.camera_enabled = false;
    }

    $("#livekit-prejoin-status").text("");

    if (audio === null && (is_video_call ? video === null : true)) {
        set_error(
            $t({
                defaultMessage:
                    "No microphone or camera detected. You can still join to watch and listen.",
            }),
        );
    } else if (audio === null) {
        set_error($t({defaultMessage: "No microphone detected."}));
    } else if (is_video_call && video === null) {
        set_error($t({defaultMessage: "No camera detected."}));
    }

    apply_mic_available(state);
    apply_camera_available(state, is_video_call);

    if (state.video_track !== null) {
        state.video_track.attach(
            document.querySelector<HTMLVideoElement>("#livekit-prejoin-video")!,
        );
    }
    apply_camera_visibility(state);
    update_toggle_button("livekit-prejoin-toggle-mic", state.mic_enabled);
    update_toggle_button("livekit-prejoin-toggle-camera", state.camera_enabled);

    if (state.audio_track !== null) {
        state.detach_meter = attach_mic_meter(
            state.audio_track,
            document.querySelector<HTMLElement>("#livekit-prejoin-meter-bar")!,
        );
    }

    await populate_all_devices(state);
}

function wire_prejoin_controls(state: PrejoinState): void {
    $("#livekit-prejoin-toggle-mic").on("click", () => {
        const track = state.audio_track;
        if (track === null) {
            return;
        }
        state.mic_enabled = !state.mic_enabled;
        if (state.mic_enabled) {
            void track.unmute();
        } else {
            void track.mute();
        }
        update_toggle_button("livekit-prejoin-toggle-mic", state.mic_enabled);
    });

    $("#livekit-prejoin-toggle-camera").on("click", () => {
        const track = state.video_track;
        if (track === null) {
            return;
        }
        state.camera_enabled = !state.camera_enabled;
        if (state.camera_enabled) {
            void track.unmute();
        } else {
            void track.mute();
        }
        update_toggle_button("livekit-prejoin-toggle-camera", state.camera_enabled);
        apply_camera_visibility(state);
    });

    const mic_select = document.querySelector<HTMLSelectElement>("#livekit-prejoin-mic-select")!;
    $(mic_select).on("change", () => {
        void switch_microphone(state, mic_select.value);
    });
    const camera_select = document.querySelector<HTMLSelectElement>(
        "#livekit-prejoin-camera-select",
    )!;
    $(camera_select).on("change", () => {
        void switch_camera(state, camera_select.value);
    });
    const speaker_select = document.querySelector<HTMLSelectElement>(
        "#livekit-prejoin-speaker-select",
    )!;
    $(speaker_select).on("change", () => {
        state.speaker_device_id = speaker_select.value;
    });
}

async function await_prejoin_decision(
    state: PrejoinState,
    call_payload: string,
): Promise<PrejoinOutcome | null> {
    return new Promise<PrejoinOutcome | null>((resolve) => {
        const cleanup = (): void => {
            if (state.detach_meter !== null) {
                state.detach_meter();
                state.detach_meter = null;
            }
            if (state.video_track !== null) {
                state.video_track.detach();
            }
        };

        // Guard against a second Join click while the token request is
        // still in flight; also blocks Cancel from firing mid-mint.
        let joining = false;

        $("#livekit-prejoin-join").on("click", () => {
            void (async () => {
                if (joining) {
                    return;
                }
                joining = true;
                $("#livekit-prejoin-join").prop("disabled", true);
                $("#livekit-prejoin-cancel").prop("disabled", true);
                $("#livekit-prejoin-status").text($t({defaultMessage: "Preparing to join…"}));
                set_error("");

                const result = await mint_livekit_token(call_payload);
                if ("error" in result) {
                    $("#livekit-prejoin-status").text("");
                    set_error(result.error);
                    joining = false;
                    $("#livekit-prejoin-join").prop("disabled", false);
                    $("#livekit-prejoin-cancel").prop("disabled", false);
                    return;
                }

                cleanup();
                $("#livekit-prejoin").prop("hidden", true);
                $("#livekit-call-main").prop("hidden", false);
                resolve({
                    prejoin: {
                        audio_track: state.audio_track,
                        video_track: state.video_track,
                        mic_enabled: state.mic_enabled,
                        camera_enabled: state.camera_enabled,
                        speaker_device_id: state.speaker_device_id,
                    },
                    token: result.token,
                });
            })();
        });

        $("#livekit-prejoin-cancel").on("click", () => {
            if (joining) {
                return;
            }
            cleanup();
            if (state.audio_track !== null) {
                state.audio_track.stop();
            }
            if (state.video_track !== null) {
                state.video_track.stop();
            }
            // Set the fallback status before window.close() so the user sees
            // it if close() no-ops (tab not opened by a script).
            $("#livekit-prejoin-status").text($t({defaultMessage: "Call canceled."}));
            resolve(null);
            window.close();
        });
    });
}

export async function run_prejoin(
    is_video_call: boolean,
    call_payload: string,
): Promise<PrejoinOutcome | null> {
    $("#livekit-prejoin").prop("hidden", false);
    $("#livekit-call-main").prop("hidden", true);

    const state: PrejoinState = {
        audio_track: null,
        video_track: null,
        mic_enabled: true,
        camera_enabled: is_video_call,
        speaker_device_id: null,
        detach_meter: null,
    };

    await setup_prejoin_ui(state, is_video_call);
    wire_prejoin_controls(state);
    return await_prejoin_decision(state, call_payload);
}
