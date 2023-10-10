import * as modals from "./modals";
import * as overlays from "./overlays";

export function any_active(): boolean {
    return overlays.is_active() || modals.is_modal_open();
}
