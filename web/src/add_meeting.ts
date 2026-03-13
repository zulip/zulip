import {$t} from "./i18n.ts";
import type {Option} from "./dropdown_widget.ts";

export const OPTION_RSVP_MEETING = 1;
export const OPTION_PROPOSE_MEETING = 2;

export function get_options_for_dropdown_widget(): Option[] {
    return [
        {
            unique_id: OPTION_RSVP_MEETING,
            name: $t({defaultMessage: "RSVP Meeting"}),
            bold_current_selection: true,
        },
        {
            unique_id: OPTION_PROPOSE_MEETING,
            name: $t({defaultMessage: "Propose a meeting"}),
            bold_current_selection: true,
        },
    ];
}