import {
    ConnectionState,
    type LocalParticipant,
    type LocalTrack,
    type LocalTrackPublication,
    type Participant,
    type RemoteParticipant,
    type RemoteTrack,
    type RemoteTrackPublication,
    Room,
    RoomEvent,
    Track,
    type TrackPublication,
} from "livekit-client";
import assert from "minimalistic-assert";

import {page_params as base_page_params} from "./base_page_params.ts";
import {$t} from "./i18n.ts";

assert(base_page_params.page_type === "livekit_call");
const page_params = base_page_params;

function set_status(text: string): void {
    const el = document.querySelector("#livekit-status");
    if (el) {
        el.textContent = text;
    }
}

function create_tile_element(
    extra_class: string,
    identity: string,
    label: string,
    with_avatar: boolean,
): HTMLElement {
    const tile = document.createElement("div");
    tile.classList.add("livekit-participant-tile", extra_class);
    tile.dataset["identity"] = identity;

    if (with_avatar) {
        const avatar_el = document.createElement("div");
        avatar_el.classList.add("livekit-participant-avatar");
        avatar_el.textContent = label.trim().charAt(0) || "?";
        tile.append(avatar_el);
    }

    const name_el = document.createElement("div");
    name_el.classList.add("livekit-participant-name");
    name_el.textContent = label;
    tile.append(name_el);

    return tile;
}

function get_or_create_camera_tile(identity: string, name: string): HTMLElement {
    const grid = document.querySelector("#livekit-grid")!;
    let tile = grid.querySelector<HTMLElement>(
        `.livekit-camera-tile[data-identity="${CSS.escape(identity)}"]`,
    );
    if (!tile) {
        tile = create_tile_element("livekit-camera-tile", identity, name, true);
        grid.append(tile);
    }
    return tile;
}

function get_or_create_screenshare_tile(identity: string, label: string): HTMLElement {
    const stage = document.querySelector("#livekit-focus-stage")!;
    let tile = stage.querySelector<HTMLElement>(
        `.livekit-screenshare-tile[data-identity="${CSS.escape(identity)}"]`,
    );
    if (!tile) {
        tile = create_tile_element("livekit-screenshare-tile", identity, label, false);
        stage.append(tile);
    }
    return tile;
}

function update_layout_mode(): void {
    const container = document.querySelector("#livekit-participants")!;
    const stage = document.querySelector("#livekit-focus-stage")!;
    container.classList.toggle("livekit-focus-mode", stage.children.length > 0);
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
        tile.classList.add("livekit-local");
    }

    const element = track.attach();
    element.classList.add("livekit-media");
    if (is_screenshare) {
        element.classList.add("livekit-screenshare");
        if (is_local) {
            // Avoid echo from your own screen share's audio.
            element.muted = true;
        }
    }
    if (track.isMuted) {
        element.classList.add("livekit-muted");
    }
    tile.prepend(element);

    if (is_screenshare) {
        update_layout_mode();
    }
}

function detach_track(
    track: RemoteTrack | LocalTrack | undefined,
    participant: Participant,
    source: Track.Source,
): void {
    if (track !== undefined) {
        for (const element of track.detach()) {
            element.remove();
        }
    }

    const is_screenshare = source === Track.Source.ScreenShare;
    const container = document.querySelector(
        is_screenshare ? "#livekit-focus-stage" : "#livekit-grid",
    )!;
    const tile_class = is_screenshare ? "livekit-screenshare-tile" : "livekit-camera-tile";
    const tile = container.querySelector<HTMLElement>(
        `.${tile_class}[data-identity="${CSS.escape(participant.identity)}"]`,
    );

    // Remove the tile if it has no media left, OR if LiveKit cleared
    // publication.track before firing the unpublish event (otherwise the
    // tile would be orphaned and focus mode would stay on).
    if (tile && (track === undefined || tile.querySelectorAll(".livekit-media").length === 0)) {
        tile.remove();
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
        element.classList.toggle("livekit-muted", muted);
    }
}

function update_toggle_button(button_id: string, active: boolean): void {
    const button = document.querySelector<HTMLButtonElement>(`#${CSS.escape(button_id)}`);
    if (button) {
        button.setAttribute("aria-pressed", String(active));
        button.classList.toggle("active", active);
    }
}

function get_source_toggle_button_id(source: Track.Source): string | undefined {
    switch (source) {
        case Track.Source.Microphone:
            return "livekit-toggle-mic";
        case Track.Source.Camera:
            return "livekit-toggle-camera";
        case Track.Source.ScreenShare:
            return "livekit-toggle-screenshare";
        default:
            return undefined;
    }
}

async function setup_local_tracks(room: Room, is_video_call: boolean): Promise<void> {
    try {
        await room.localParticipant.setMicrophoneEnabled(true);
    } catch {
        // Microphone permission denied — join as listener.
    }

    if (is_video_call) {
        try {
            await room.localParticipant.setCameraEnabled(true);
        } catch {
            // Camera permission denied — join without video.
            update_toggle_button("livekit-toggle-camera", false);
        }
    } else {
        update_toggle_button("livekit-toggle-camera", false);
    }
}

function setup_controls(room: Room): void {
    document.querySelector("#livekit-toggle-mic")?.addEventListener("click", () => {
        const enabled = room.localParticipant.isMicrophoneEnabled;
        void room.localParticipant.setMicrophoneEnabled(!enabled);
        update_toggle_button("livekit-toggle-mic", !enabled);
    });

    document.querySelector("#livekit-toggle-camera")?.addEventListener("click", () => {
        const enabled = room.localParticipant.isCameraEnabled;
        void room.localParticipant.setCameraEnabled(!enabled);
        update_toggle_button("livekit-toggle-camera", !enabled);
    });

    document.querySelector("#livekit-toggle-screenshare")?.addEventListener("click", () => {
        const enabled = room.localParticipant.isScreenShareEnabled;
        void room.localParticipant.setScreenShareEnabled(!enabled);
        update_toggle_button("livekit-toggle-screenshare", !enabled);
    });

    document.querySelector("#livekit-leave")?.addEventListener("click", () => {
        void (async () => {
            await room.disconnect();
            window.close();
            // If window.close() doesn't work (e.g., tab wasn't opened by script),
            // show a message.
            set_status($t({defaultMessage: "Call ended."}));
            document.querySelector("#livekit-controls")?.remove();
        })();
    });
}

async function main(): Promise<void> {
    const room = new Room();

    room.on(
        RoomEvent.TrackSubscribed,
        (track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
            attach_track(track, participant, false);
        },
    )
        .on(
            RoomEvent.TrackUnsubscribed,
            (track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
                detach_track(track, participant, track.source);
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
                    // publication.track may already be undefined — detach_track
                    // handles that and force-removes the tile.
                    detach_track(publication.track, participant, publication.source);
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
            const container = document.querySelector("#livekit-participants")!;
            const tiles = container.querySelectorAll<HTMLElement>(
                `.livekit-participant-tile[data-identity="${CSS.escape(participant.identity)}"]`,
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

    setup_controls(room);

    try {
        set_status($t({defaultMessage: "Connecting…"}));
        await room.connect(page_params.livekit_url, page_params.token);
        set_status("");
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        set_status($t({defaultMessage: "Failed to connect: {message}"}, {message}));
        return;
    }

    await setup_local_tracks(room, page_params.is_video_call);

    // Attach tracks from participants already in the room.
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
    local_tile.classList.add("livekit-local");

    room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Disconnected) {
            set_status($t({defaultMessage: "Disconnected."}));
        }
    });
}

void main();
