import $ from "jquery";

export function enable(): void {
    $("body").removeClass("color-scheme-automatic").addClass("dark-theme");
}

export function disable(): void {
    $("body").removeClass("color-scheme-automatic").removeClass("dark-theme");
}

export function default_preference_checker(): void {
    $("body").removeClass("dark-theme").addClass("color-scheme-automatic");
}
