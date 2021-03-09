export function enable() {
    $("body").removeClass("color-scheme-automatic").addClass("night-mode");
}

export function disable() {
    $("body").removeClass("color-scheme-automatic").removeClass("night-mode");
}

export function default_preference_checker() {
    $("body").removeClass("night-mode").addClass("color-scheme-automatic");
}
