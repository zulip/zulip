import $ from "jquery";
import {
    type LocalAudioTrack,
    type LocalParticipant,
    type LocalTrack,
    type LocalTrackPublication,
    type LocalVideoTrack,
    type Participant,
    type RemoteParticipant,
    type RemoteTrack,
    type RemoteTrackPublication,
    Room,
    RoomEvent,
    Track,
    type TrackPublication,
} from "livekit-client";

import {$t} from "./i18n.ts";

export function update_toggle_button(button_id: string, active: boolean): void {
    const $button = $(`#${CSS.escape(button_id)}`);
    $button.attr("aria-pressed", String(active));
    $button.toggleClass("active", active);
}

export type PrejoinResult = {
    audio_track: LocalAudioTrack | null;
    video_track: LocalVideoTrack | null;
    mic_enabled: boolean;
    camera_enabled: boolean;
    speaker_device_id: string | null;
};

export type RoomConnectionParams = {
    livekit_url: string;
    token: string;
    is_video_call: boolean;
};

function set_status(text: string): void {
    $("#livekit-call-status").text(text);
}

function create_tile_element(
    extra_class: string,
    identity: string,
    label: string,
    with_avatar: boolean,
): HTMLElement {
    const $tile = $("<div>")
        .addClass("livekit-call-participant-tile")
        .addClass(extra_class)
        .attr("data-identity", identity);

    if (with_avatar) {
        $tile.append(
            $("<div>")
                .addClass("livekit-call-participant-avatar")
                .text(label.trim().charAt(0) || "?"),
        );
    }

    $tile.append($("<div>").addClass("livekit-call-participant-name").text(label));

    return $tile[0]!;
}

function get_or_create_camera_tile(identity: string, name: string): HTMLElement {
    const grid = document.querySelector<HTMLElement>("#livekit-call-grid")!;
    let tile = grid.querySelector<HTMLElement>(
        `.livekit-call-camera-tile[data-identity="${CSS.escape(identity)}"]`,
    );
    if (!tile) {
        tile = create_tile_element("livekit-call-camera-tile", identity, name, true);
        grid.append(tile);
    }
    return tile;
}

function get_or_create_screenshare_tile(identity: string, label: string): HTMLElement {
    const stage = document.querySelector<HTMLElement>("#livekit-call-focus-stage")!;
    let tile = stage.querySelector<HTMLElement>(
        `.livekit-call-screenshare-tile[data-identity="${CSS.escape(identity)}"]`,
    );
    if (!tile) {
        tile = create_tile_element("livekit-call-screenshare-tile", identity, label, false);
        stage.append(tile);
    }
    return tile;
}

function update_layout_mode(): void {
    const stage = document.querySelector<HTMLElement>("#livekit-call-focus-stage")!;
    $("#livekit-call-participants").toggleClass(
        "livekit-call-focus-mode",
        stage.children.length > 0,
    );
}

function attach_track(
    track: RemoteTrack | LocalTrack,
    participant: Participant,
    is_local: boolean,
): void {
    const is_screenshare = track.source === Track.Source.ScreenShare;
    const name = participant.name ?? participant.identity;

    let label: string;
    if (is_local && is_screenshare) {
        label = $t({defaultMessage: "{name} (your screen)"}, {name});
    } else if (is_local) {
        label = $t({defaultMessage: "{name} (you)"}, {name});
    } else if (is_screenshare) {
        label = $t({defaultMessage: "{name} (screen)"}, {name});
    } else {
        label = name;
    }

    const tile = is_screenshare
        ? get_or_create_screenshare_tile(participant.identity, label)
        : get_or_create_camera_tile(participant.identity, label);

    if (is_local) {
        tile.classList.add("livekit-call-local");
    }

    const element = track.attach();
    element.classList.add("livekit-call-media");
    element.dataset["source"] = track.source;
    if (is_screenshare) {
        element.classList.add("livekit-call-screenshare");
        if (is_local) {
            // Avoid echo from your own screen share's audio.
            element.muted = true;
        }
    }
    if (track.isMuted) {
        element.classList.add("livekit-call-muted");
    }
    tile.prepend(element);

    if (is_screenshare) {
        update_layout_mode();
    }
}

function detach_track(participant: Participant, source: Track.Source): void {
    const is_screenshare = source === Track.Source.ScreenShare;
    const container = document.querySelector<HTMLElement>(
        is_screenshare ? "#livekit-call-focus-stage" : "#livekit-call-grid",
    )!;
    const tile_class = is_screenshare
        ? "livekit-call-screenshare-tile"
        : "livekit-call-camera-tile";
    const tile = container.querySelector<HTMLElement>(
        `.${tile_class}[data-identity="${CSS.escape(participant.identity)}"]`,
    );

    if (tile) {
        for (const element of tile.querySelectorAll(
            `.livekit-call-media[data-source="${CSS.escape(source)}"]`,
        )) {
            element.remove();
        }
        // The screenshare tile is dedicated to a single screenshare video
        // track, so it goes away when that track ends. The camera tile
        // stays so the avatar placeholder shows when there's no video.
        if (is_screenshare) {
            tile.remove();
        }
    }

    if (is_screenshare) {
        update_layout_mode();
    }
}

function set_media_muted_class(publication: TrackPublication, muted: boolean): void {
    if (publication.kind !== Track.Kind.Video) {
        return;
    }
    const elements = publication.track?.attachedElements ?? [];
    for (const element of elements) {
        element.classList.toggle("livekit-call-muted", muted);
    }
}

function get_source_toggle_button_id(source: Track.Source): string | undefined {
    switch (source) {
        case Track.Source.Microphone:
            return "livekit-call-toggle-mic";
        case Track.Source.Camera:
            return "livekit-call-toggle-camera";
        case Track.Source.ScreenShare:
            return "livekit-call-toggle-screenshare";
        default:
            return undefined;
    }
}

function setup_controls(room: Room, camera_available: boolean): void {
    // The toggle buttons' visible state is updated by the room's
    // TrackMuted / TrackUnmuted / LocalTrackPublished / LocalTrackUnpublished
    // listeners registered in start_in_call; the click handlers only kick
    // off the async state change and guard against double-click races.
    async function toggle(
        $button: JQuery,
        set: (enabled: boolean) => Promise<unknown>,
        read: () => boolean,
    ): Promise<void> {
        if ($button.prop("disabled")) {
            return;
        }
        $button.prop("disabled", true);
        try {
            await set(!read());
        } finally {
            $button.prop("disabled", false);
        }
    }

    const $mic_button = $("#livekit-call-toggle-mic");
    $mic_button.on("click", () => {
        void toggle(
            $mic_button,
            async (enabled) => room.localParticipant.setMicrophoneEnabled(enabled),
            () => room.localParticipant.isMicrophoneEnabled,
        );
    });

    const $camera_button = $("#livekit-call-toggle-camera");
    if (!camera_available) {
        $camera_button.prop("disabled", true);
    } else {
        $camera_button.on("click", () => {
            void toggle(
                $camera_button,
                async (enabled) => room.localParticipant.setCameraEnabled(enabled),
                () => room.localParticipant.isCameraEnabled,
            );
        });
    }

    const $screenshare_button = $("#livekit-call-toggle-screenshare");
    $screenshare_button.on("click", () => {
        void toggle(
            $screenshare_button,
            async (enabled) => room.localParticipant.setScreenShareEnabled(enabled),
            () => room.localParticipant.isScreenShareEnabled,
        );
    });

    $("#livekit-call-leave").on("click", () => {
        void (async () => {
            await room.disconnect();
            // Set the fallback UI before window.close() so the user sees it
            // if close() no-ops (which happens when the tab wasn't opened by
            // a script).
            set_status($t({defaultMessage: "Call ended."}));
            $("#livekit-call-controls").remove();
            window.close();
        })();
    });
}

async function apply_speaker_device(room: Room, device_id: string | null): Promise<void> {
    if (device_id === null) {
        return;
    }
    if (!("setSinkId" in HTMLMediaElement.prototype)) {
        return;
    }
    try {
        await room.switchActiveDevice("audiooutput", device_id);
    } catch {
        // Speaker switching is best-effort; some browsers refuse specific IDs.
    }
}

async function publish_prejoin_tracks(room: Room, prejoin: PrejoinResult): Promise<void> {
    if (prejoin.audio_track !== null) {
        try {
            await room.localParticipant.publishTrack(prejoin.audio_track, {
                source: Track.Source.Microphone,
            });
            if (!prejoin.mic_enabled) {
                await prejoin.audio_track.mute();
            }
        } catch {
            // Publishing failed; user can retry via the in-call toggle.
        }
    }
    if (prejoin.video_track !== null) {
        try {
            await room.localParticipant.publishTrack(prejoin.video_track, {
                source: Track.Source.Camera,
            });
            if (!prejoin.camera_enabled) {
                await prejoin.video_track.mute();
            }
        } catch {
            // Publishing failed; user can retry via the in-call toggle.
        }
    }
}

function register_room_listeners(room: Room): void {
    room.on(
        RoomEvent.TrackSubscribed,
        (track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
            attach_track(track, participant, false);
        },
    )
        .on(
            RoomEvent.TrackUnsubscribed,
            (track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
                detach_track(participant, track.source);
            },
        )
        .on(
            RoomEvent.LocalTrackPublished,
            (publication: LocalTrackPublication, participant: LocalParticipant) => {
                if (
                    publication.track &&
                    (publication.source === Track.Source.Camera ||
                        publication.source === Track.Source.ScreenShare)
                ) {
                    attach_track(publication.track, participant, true);
                }
                const button_id = get_source_toggle_button_id(publication.source);
                if (button_id !== undefined) {
                    update_toggle_button(button_id, !publication.isMuted);
                }
            },
        )
        .on(
            RoomEvent.LocalTrackUnpublished,
            (publication: LocalTrackPublication, participant: LocalParticipant) => {
                if (
                    publication.source === Track.Source.Camera ||
                    publication.source === Track.Source.ScreenShare
                ) {
                    detach_track(participant, publication.source);
                }
                const button_id = get_source_toggle_button_id(publication.source);
                if (button_id !== undefined) {
                    update_toggle_button(button_id, false);
                }
            },
        )
        .on(RoomEvent.TrackMuted, (publication: TrackPublication, participant: Participant) => {
            set_media_muted_class(publication, true);
            if (participant === room.localParticipant) {
                const button_id = get_source_toggle_button_id(publication.source);
                if (button_id !== undefined) {
                    update_toggle_button(button_id, false);
                }
            }
        })
        .on(RoomEvent.TrackUnmuted, (publication: TrackPublication, participant: Participant) => {
            set_media_muted_class(publication, false);
            if (participant === room.localParticipant) {
                const button_id = get_source_toggle_button_id(publication.source);
                if (button_id !== undefined) {
                    update_toggle_button(button_id, true);
                }
            }
        })
        .on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
            get_or_create_camera_tile(
                participant.identity,
                participant.name ?? participant.identity,
            );
        })
        .on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
            const container = document.querySelector<HTMLElement>("#livekit-call-participants")!;
            const tiles = container.querySelectorAll<HTMLElement>(
                `.livekit-call-participant-tile[data-identity="${CSS.escape(participant.identity)}"]`,
            );
            for (const tile of tiles) {
                tile.remove();
            }
            update_layout_mode();
        })
        .on(RoomEvent.Reconnecting, () => {
            set_status($t({defaultMessage: "Reconnecting…"}));
        })
        .on(RoomEvent.Reconnected, () => {
            set_status("");
        })
        .on(RoomEvent.Disconnected, () => {
            set_status($t({defaultMessage: "Disconnected."}));
        });
}

function sync_initial_participants(room: Room): void {
    // Attach tracks from participants already in the room when we joined.
    for (const participant of room.remoteParticipants.values()) {
        get_or_create_camera_tile(participant.identity, participant.name ?? participant.identity);
        for (const publication of participant.trackPublications.values()) {
            if (publication.isSubscribed && publication.track) {
                attach_track(publication.track, participant, false);
            }
        }
    }

    // Show a placeholder local tile for voice calls and when camera is unavailable.
    const local = room.localParticipant;
    const local_tile = get_or_create_camera_tile(
        local.identity,
        $t({defaultMessage: "{name} (you)"}, {name: local.name ?? local.identity}),
    );
    local_tile.classList.add("livekit-call-local");
}

export async function start_in_call(
    params: RoomConnectionParams,
    prejoin: PrejoinResult,
): Promise<void> {
    const camera_available = params.is_video_call && prejoin.video_track !== null;
    const room = new Room();

    register_room_listeners(room);
    setup_controls(room, camera_available);
    update_toggle_button("livekit-call-toggle-mic", prejoin.mic_enabled);
    update_toggle_button("livekit-call-toggle-camera", prejoin.camera_enabled);

    try {
        set_status($t({defaultMessage: "Connecting…"}));
        await room.connect(params.livekit_url, params.token);
        set_status("");
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        set_status($t({defaultMessage: "Failed to connect: {message}"}, {message}));
        return;
    }

    await publish_prejoin_tracks(room, prejoin);
    await apply_speaker_device(room, prejoin.speaker_device_id);
    sync_initial_participants(room);
}
