import * as components from "./components";
import {$t} from "./i18n";

let toggler;

export function set_toggler(instance) {
    toggler = instance;
}

export function create_toggler(callback) {
    return components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Personal"}), key: "settings"},
            {label: $t({defaultMessage: "Organization"}), key: "organization"},
        ],
        callback,
    });
}

export function goto(tab_name) {
    if (toggler) {
        toggler.goto(tab_name);
    }
}
