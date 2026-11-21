import {localstorage} from "./localstorage.ts";

export type StickySenderDemoMode = "avatars" | "names" | "both";

const MODE_KEY = "stickySenderDemoMode";

export function get_mode(): StickySenderDemoMode {
    const mode: unknown = localstorage.supported() ? localstorage().get(MODE_KEY) : undefined;
    if (mode === "avatars" || mode === "names") {
        return mode;
    }
    return "both";
}

export function set_mode(mode: StickySenderDemoMode): void {
    if (localstorage.supported()) {
        localstorage().set(MODE_KEY, mode);
    }
}

export function sticky_avatars_enabled(): boolean {
    return get_mode() !== "names";
}

export function sticky_names_enabled(): boolean {
    return get_mode() !== "avatars";
}
