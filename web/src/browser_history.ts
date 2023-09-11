// TODO: Rewrite this module to use history.pushState.

import * as blueslip from "./blueslip";
import * as hash_util from "./hash_util";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";

export const state: {
    is_internal_change: boolean;
    hash_before_overlay: string | null;
    old_hash: string;
    changing_hash: boolean;
    spectator_old_hash: string | null;
} = {
    is_internal_change: false,
    hash_before_overlay: null,
    old_hash: window.location.hash,
    changing_hash: false,
    // If the spectator's hash changes to a restricted hash, then we store the old hash
    // so that we can take user back to the allowed hash.
    // TODO: Store #narrow old hashes. Currently they are not stored here since, the #narrow
    // hashes are changed without calling `hashchanged` in many ways.
    spectator_old_hash: hash_util.is_spectator_compatible(window.location.hash)
        ? window.location.hash
        : null,
};

export function clear_for_testing(): void {
    state.is_internal_change = false;
    state.hash_before_overlay = null;
    state.old_hash = "#";
}

export function old_hash(): string {
    return state.old_hash;
}

export function set_hash_before_overlay(hash: string): void {
    state.hash_before_overlay = hash;
}

export function update_web_public_hash(hash: string): boolean {
    // Returns true if hash is web-public compatible.
    if (hash_util.is_spectator_compatible(hash)) {
        state.spectator_old_hash = hash;
        return true;
    }
    return false;
}

export function save_old_hash(): boolean {
    state.old_hash = window.location.hash;

    const was_internal_change = state.is_internal_change;
    state.is_internal_change = false;

    return was_internal_change;
}

export function update(new_hash: string): void {
    const old_hash = window.location.hash;

    if (!new_hash.startsWith("#")) {
        blueslip.error("programming error: prefix hashes with #", {new_hash});
        return;
    }

    if (old_hash === new_hash) {
        // If somebody is calling us with the same hash we already have, it's
        // probably harmless, and we just ignore it.  But it could be a symptom
        // of disorganized code that's prone to an infinite loop of repeatedly
        // assigning the same hash.
        blueslip.info("ignoring probably-harmless call to browser_history.update: " + new_hash);
        return;
    }

    state.old_hash = old_hash;
    state.is_internal_change = true;
    window.location.hash = new_hash;
}

export function exit_overlay(): void {
    if (hash_util.is_overlay_hash(window.location.hash) && !state.changing_hash) {
        ui_util.blur_active_element();
        const new_hash = state.hash_before_overlay || `#${user_settings.default_view}`;
        update(new_hash);
    }
}

export function go_to_location(hash: string): void {
    // Call this function when you WANT the hashchanged
    // function to run.
    window.location.hash = hash;
}

export function update_hash_internally_if_required(hash: string): void {
    if (window.location.hash !== hash) {
        update(hash);
    }
}

export function return_to_web_public_hash(): void {
    window.location.hash = state.spectator_old_hash ?? `#${user_settings.default_view}`;
}
