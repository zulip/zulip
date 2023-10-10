import * as overlays from './overlays';

export function any_active(): boolean {
    return overlays.is_active() || overlays.is_modal_open();
}
