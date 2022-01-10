import $ from "jquery";

export function enable(): void {
    if (typeof Storage !== "undefined") {
        localStorage.setItem("theme-value", "dark-theme");
    } else {
        // Sorry! No Web Storage support..
    }
    $("body").removeClass("color-scheme-automatic").addClass("dark-theme");
}

export function disable(): void {
    if (typeof Storage !== "undefined") {
        localStorage.setItem("theme-value", "light-theme");
    } else {
        // Sorry! No Web Storage support..
    }
    $("body").removeClass("color-scheme-automatic").removeClass("dark-theme");
}

export function default_preference_checker(): void {
    if (typeof Storage !== "undefined") {
        localStorage.setItem("theme-value", "light-theme");
    } else {
        // Sorry! No Web Storage support..
    }
    $("body").removeClass("dark-theme").addClass("color-scheme-automatic");
}
