import {
    ConnectionState,
    type RemoteParticipant,
    type RemoteTrack,
    type RemoteTrackPublication,
    Room,
    RoomEvent,
    Track,
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

function create_participant_tile(identity: string, name: string): HTMLElement {
    const tile = document.createElement("div");
    tile.classList.add("livekit-participant-tile");
    tile.dataset["identity"] = identity;

    const label = document.createElement("div");
    label.classList.add("livekit-participant-name");
    label.textContent = name;
    tile.append(label);

    return tile;
}

function get_or_create_tile(identity: string, name: string): HTMLElement {
    const container = document.querySelector("#livekit-participants")!;
    let tile = container.querySelector<HTMLElement>(
        `.livekit-participant-tile[data-identity="${CSS.escape(identity)}"]`,
    );
    if (!tile) {
        tile = create_participant_tile(identity, name);
        container.append(tile);
    }
    return tile;
}

function attach_track(track: RemoteTrack, participant: RemoteParticipant): void {
    const tile = get_or_create_tile(participant.identity, participant.name ?? participant.identity);

    const element = track.attach();
    element.classList.add("livekit-media");
    if (track.source === Track.Source.ScreenShare) {
        element.classList.add("livekit-screenshare");
    }
    tile.prepend(element);
}

function detach_track(track: RemoteTrack, participant: RemoteParticipant): void {
    for (const element of track.detach()) {
        element.remove();
    }

    const container = document.querySelector("#livekit-participants")!;
    const tile = container.querySelector<HTMLElement>(
        `.livekit-participant-tile[data-identity="${CSS.escape(participant.identity)}"]`,
    );
    if (tile?.querySelectorAll(".livekit-media").length === 0) {
        tile.remove();
    }
}

function update_toggle_button(button_id: string, active: boolean): void {
    const button = document.querySelector<HTMLButtonElement>(`#${CSS.escape(button_id)}`);
    if (button) {
        button.setAttribute("aria-pressed", String(active));
        button.classList.toggle("active", active);
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
            attach_track(track, participant);
        },
    )
        .on(
            RoomEvent.TrackUnsubscribed,
            (track: RemoteTrack, _pub: RemoteTrackPublication, participant: RemoteParticipant) => {
                detach_track(track, participant);
            },
        )
        .on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
            get_or_create_tile(participant.identity, participant.name ?? participant.identity);
        })
        .on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
            const container = document.querySelector("#livekit-participants")!;
            container
                .querySelector(
                    `.livekit-participant-tile[data-identity="${CSS.escape(participant.identity)}"]`,
                )
                ?.remove();
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
        get_or_create_tile(participant.identity, participant.name ?? participant.identity);
        for (const publication of participant.trackPublications.values()) {
            if (publication.isSubscribed && publication.track) {
                attach_track(publication.track, participant);
            }
        }
    }

    // Handle local participant video preview.
    const local = room.localParticipant;
    const local_tile = get_or_create_tile(local.identity, local.name ?? local.identity);
    local_tile.classList.add("livekit-local");
    for (const pub of local.trackPublications.values()) {
        if (pub.track?.source === Track.Source.Camera) {
            const el = pub.track.attach();
            el.classList.add("livekit-media");
            local_tile.prepend(el);
        }
    }

    room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Disconnected) {
            set_status($t({defaultMessage: "Disconnected."}));
        }
    });
}

void main();
