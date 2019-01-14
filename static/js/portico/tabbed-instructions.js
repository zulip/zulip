export function detect_user_os() {
    if (/Android/i.test(navigator.userAgent)) {
        return "android";
    }
    if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        return "ios";
    }
    if (/Mac/i.test(navigator.userAgent)) {
        return "mac";
    }
    if (/Win/i.test(navigator.userAgent)) {
        return "windows";
    }
    if (/Linux/i.test(navigator.userAgent)) {
        return "linux";
    }
    return "mac"; // if unable to determine OS return Mac by default
}

export function activate_correct_tab($codeSection) {
    var user_os = detect_user_os();
    var desktop_os = ["mac", "linux", "windows"];
    const $li = $codeSection.find("ul.nav li");
    const $blocks = $codeSection.find(".blocks div");

    $li.each(function () {
        const language = this.dataset.language;
        $(this).removeClass("active");
        if (language === user_os) {
            $(this).addClass("active");
        }

        if (desktop_os.indexOf(user_os) !== -1 && language === "desktop-web") {
            $(this).addClass("active");
        }
    });

    $blocks.each(function () {
        const language = this.dataset.language;
        $(this).removeClass("active");
        if (language === user_os) {
            $(this).addClass("active");
        }

        if (desktop_os.indexOf(user_os) !== -1 && language === "desktop-web") {
            $(this).addClass("active");
        }
    });

    // if no tab was activated, just activate the first one
    var active_list_items = $li.filter(".active");
    if (!active_list_items.length) {
        $li.first().addClass("active");
        var language = $li.first()[0].dataset.language;
        $blocks.filter("[data-language=" + language + "]").addClass("active");
    }
}

(function () {
$(".code-section").each(function () {
    activate_correct_tab($(this));
});
}());
