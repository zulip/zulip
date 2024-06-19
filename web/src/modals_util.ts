import {$t} from "./i18n";

export const custom_time_unit_values = {
    minutes: {
        name: "minutes",
        description: $t({defaultMessage: "minutes"}),
    },
    hours: {
        name: "hours",
        description: $t({defaultMessage: "hours"}),
    },
    days: {
        name: "days",
        description: $t({defaultMessage: "days"}),
    },
    weeks: {
        name: "weeks",
        description: $t({defaultMessage: "weeks"}),
    },
};

export function get_custom_time_in_minutes(time_unit: string, time_input: number): number {
    switch (time_unit) {
        case "hours":
            return time_input * 60;
        case "days":
            return time_input * 24 * 60;
        case "weeks":
            return time_input * 7 * 24 * 60;
        default:
            return time_input;
    }
}
