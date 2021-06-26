import $ from "jquery";

export function enable(): void {
    $("body").removeClass("color-scheme-automatic").addClass("night-mode");
}

export function disable(): void {
    $("body").removeClass("color-scheme-automatic").removeClass("night-mode");
}

export function default_preference_checker(): void {
    $("body").removeClass("night-mode").addClass("color-scheme-automatic");
}
