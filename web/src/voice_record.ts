import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import * as upload from "./upload.ts";

// Preferred recording MIME types, most-preferred first. Every entry is present
// in upload.ts's SUPPORTED_AUDIO_TYPES (mirroring the server's
// AUDIO_INLINE_MIME_TYPES allowlist), so a recording uploaded with one of these
// types renders with the native inline <audio> player. MP4/AAC is preferred
// because it plays on every platform, including Safari/iOS; Opus-in-WebM is the
// fallback (smaller, but not playable on Apple platforms).
const recording_mime_candidates = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"];

type RecordingSession = {
    recorder: MediaRecorder;
    stream: MediaStream;
    chunks: Blob[];
    $button: JQuery;
    // The MIME type we asked MediaRecorder to use, or "" if we let it pick.
    requested_mime_type: string;
    timer_interval_id: ReturnType<typeof setInterval>;
    started_at: number;
    // Set when the user cancels, so the "stop" handler discards the recording
    // instead of uploading it.
    cancelled: boolean;
};

let session: RecordingSession | undefined;

export function is_supported(): boolean {
    return (
        typeof MediaRecorder !== "undefined" &&
        typeof navigator !== "undefined" &&
        navigator.mediaDevices?.getUserMedia !== undefined
    );
}

function pick_mime_type(): string | undefined {
    if (typeof MediaRecorder.isTypeSupported !== "function") {
        // Older browsers: let MediaRecorder choose its default container.
        return undefined;
    }
    return recording_mime_candidates.find((mime_type) => MediaRecorder.isTypeSupported(mime_type));
}

// MediaRecorder reports blob types such as "audio/webm;codecs=opus", but the
// upload code matches file.type by exact membership in SUPPORTED_AUDIO_TYPES,
// so we drop the codecs parameter before constructing the File. Without this,
// the message renders as a plain download link instead of an inline player.
export function normalize_audio_mime_type(mime_type: string): string {
    return (mime_type.split(";")[0] ?? "").trim();
}

export function extension_for_mime_type(mime_type: string): string {
    switch (mime_type) {
        case "audio/mp4":
            return "m4a";
        case "audio/mpeg":
            return "mp3";
        case "audio/wav":
        case "audio/x-wav":
        case "audio/vnd.wave":
            return "wav";
        case "audio/webm":
            // ".weba" is the audio/webm extension; ".webm" is video/webm, which
            // makes the server render the upload as a video player, not audio.
            return "weba";
        default:
            return "weba";
    }
}

function format_elapsed(milliseconds: number): string {
    const total_seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(total_seconds / 60);
    const seconds = total_seconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function update_recording_label(): void {
    if (session === undefined) {
        return;
    }
    const elapsed = format_elapsed(performance.now() - session.started_at);
    session.$button.attr(
        "aria-label",
        $t({defaultMessage: "Recording {elapsed}; click to send, Esc to cancel"}, {elapsed}),
    );
}

export function toggle_recording($button: JQuery): void {
    if (session === undefined) {
        void start_recording($button);
    } else {
        stop_and_send();
    }
}

async function start_recording($button: JQuery): Promise<void> {
    if (!is_supported()) {
        blueslip.warn("Voice recording is not supported in this browser.");
        return;
    }

    let stream: MediaStream;
    try {
        stream = await navigator.mediaDevices.getUserMedia({audio: true});
    } catch (error) {
        // Most commonly the user denied the microphone-permission prompt.
        blueslip.warn(`Could not start voice recording: ${String(error)}`);
        return;
    }

    const requested_mime_type = pick_mime_type();
    const recorder = new MediaRecorder(
        stream,
        requested_mime_type === undefined ? {} : {mimeType: requested_mime_type},
    );
    const chunks: Blob[] = [];

    session = {
        recorder,
        stream,
        chunks,
        $button,
        requested_mime_type: requested_mime_type ?? "",
        started_at: performance.now(),
        timer_interval_id: setInterval(update_recording_label, 500),
        cancelled: false,
    };

    recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
            chunks.push(event.data);
        }
    });
    recorder.addEventListener("stop", handle_recorder_stop);

    recorder.start();
    $button.addClass("recording");
    update_recording_label();
    $(document).on("keydown.voice_record", (event) => {
        if (event.key === "Escape") {
            cancel_recording();
        }
    });
}

function stop_and_send(): void {
    // The upload happens in the recorder's "stop" handler, once the final audio
    // chunk has been flushed.
    session?.recorder.stop();
}

export function cancel_recording(): void {
    if (session === undefined) {
        return;
    }
    session.cancelled = true;
    session.recorder.stop();
}

function handle_recorder_stop(): void {
    if (session === undefined) {
        return;
    }
    const {chunks, cancelled} = session;
    const mime_type = normalize_audio_mime_type(
        session.requested_mime_type === ""
            ? session.recorder.mimeType
            : session.requested_mime_type,
    );

    teardown_session();

    if (cancelled || chunks.length === 0) {
        return;
    }

    const filename = `voice-message.${extension_for_mime_type(mime_type)}`;
    const recorded_file = new File(chunks, filename, {type: mime_type});
    upload.upload_recorded_audio_file(recorded_file);
}

function teardown_session(): void {
    if (session === undefined) {
        return;
    }
    clearInterval(session.timer_interval_id);
    for (const track of session.stream.getTracks()) {
        track.stop();
    }
    session.$button.removeClass("recording");
    session.$button.attr("aria-label", $t({defaultMessage: "Record voice message"}));
    $(document).off("keydown.voice_record");
    session = undefined;
}
