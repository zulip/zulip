const ELECTRON_APP_VERSION = "1.9.0";
const ELECTRON_APP_URL_LINUX = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + "-x86_64.AppImage";
const ELECTRON_APP_URL_MAC = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-" + ELECTRON_APP_VERSION + ".dmg";
const ELECTRON_APP_URL_WINDOWS = "https://github.com/zulip/zulip-electron/releases/download/v" + ELECTRON_APP_VERSION + "/Zulip-Web-Setup-" + ELECTRON_APP_VERSION + ".exe";

import render_tabs from './team.js';

// this will either smooth scroll to an anchor where the `name`
// is the same as the `scroll-to` reference, or to a px height
// (as specified like `scroll-to='0px'`).
var ScrollTo = function () {
    $("[scroll-to]").click(function () {
        var sel = $(this).attr("scroll-to");

        // if the `scroll-to` is a parse-able pixel value like `50px`,
        // then use that as the scrollTop, else assume it is a selector name
        // and find the `offsetTop`.
        var top = /\dpx/.test(sel) ?
                parseInt(sel, 10) :
                $("[name='" + sel + "']").offset().top;

        $("body").animate({ scrollTop: top + "px" }, 300);
    });
};

export function path_parts() {
    return window.location.pathname.split('/').filter(function (chunk) {
        return chunk !== '';
    });
}

var hello_events = function () {
    var counter = 0;
    $(window).scroll(function () {
        if (counter % 2 === 0) {
            $(".screen.hero-screen .message-feed").css("transform", "translateY(-" + $(this).scrollTop() / 5 + "px)");
        }
        counter += 1;
    });

    $(".footer").addClass("hello");
};

var apps_events = function () {
    var info = {
        windows: {
            image: "/static/images/landing-page/microsoft.png",
            alt: "Windows",
            description: "Zulip for Windows is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_WINDOWS,
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide#installing-on-windows",
        },
        mac: {
            image: "/static/images/landing-page/macbook.png",
            alt: "macOS",
            description: "Zulip on macOS is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_MAC,
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide#installing-on-macos",
        },
        android: {
            image: "/static/images/app-screenshots/zulip-android.png",
            alt: "Android",
            description: "Zulip's native Android app makes it easy to keep up while on the go.",
            link: "https://play.google.com/store/apps/details?id=com.zulipmobile",
        },
        ios: {
            image: "/static/images/app-screenshots/zulip-iphone-rough.png",
            alt: "iOS",
            description: "Zulip's native iOS app makes it easy to keep up while on the go.",
            link: "https://itunes.apple.com/us/app/zulip/id1203036395",
        },
        linux: {
            image: "/static/images/landing-page/ubuntu.png",
            alt: "Linux",
            description: "Zulip on the Linux desktop is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            link: ELECTRON_APP_URL_LINUX,
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide#installing-on-linux",
        },
    };

    var version;

    function get_user_os() {
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

    function get_version_from_path() {
        var result;
        var parts = path_parts();

        Object.keys(info).forEach(function (version) {
            if (parts.includes(version)) {
                result = version;
            }
        });

        result = result || get_user_os();
        return result;
    }

    function get_path_from_version() {
        return '/apps/' + version;
    }

    function update_path() {
        var next_path = get_path_from_version();
        history.pushState(version, '', next_path);
    }

    var update_page = function () {
        var $download_instructions = $(".download-instructions");
        var version_info = info[version];

        $(".info .platform").text(version_info.alt);
        $(".info .description").text(version_info.description);
        $(".info .link").attr("href", version_info.link);
        $(".image img").attr("src", version_info.image);
        $download_instructions.find("a").attr("href", version_info.install_guide);

        if (version_info.show_instructions) {
            $download_instructions.show();
        } else {
            $download_instructions.hide();
        }
    };

    $(window).on('popstate', function () {
        version = get_version_from_path();
        update_page();
        $("body").animate({ scrollTop: 0 }, 200);
    });

    $(".apps a .icon").click(function (e) {
        var next_version = $(e.target).closest('a')
            .attr('href')
            .replace('/apps/', '');
        version = next_version;

        update_path();
        update_page();
        $("body").animate({ scrollTop: 0 }, 200);

        return false;
    });

    // init
    version = get_version_from_path();
    history.replaceState(version, '', get_path_from_version());
    update_page();
};

var events = function () {
    ScrollTo();

    $("a").click(function (e) {
        // if a user is holding the CMD/CTRL key while clicking a link, they
        // want to open the link in another browser tab which means that we
        // should preserve the state of this one. Return out, and don't fade
        // the page.
        if (e.metaKey || e.ctrlKey) {
            return;
        }

        // if the pathname is different than what we are already on, run the
        // custom transition function.
        if (window.location.pathname !== this.pathname && !this.hasAttribute("download") &&
            !/no-action/.test(this.className)) {
            e.preventDefault();
            $(".portico-landing").removeClass("show");
            setTimeout(function () {
                window.location.href = $(this).attr("href");
            }.bind(this), 500);
        }
    });

    // get the location url like `zulipchat.com/features/`, cut off the trailing
    // `/` and then split by `/` to get ["zulipchat.com", "features"], then
    // pop the last element to get the current section (eg. `features`).
    var location = window.location.pathname.replace(/\/#*$/, "").split(/\//).pop();

    $("[on-page='" + location + "']").addClass("active");

    $("body").click(function (e) {
        var $e = $(e.target);

        if ($e.is("nav ul .exit")) {
            $("nav ul").removeClass("show");
        }

        if ($("nav ul.show") && !$e.closest("nav ul.show").length && !$e.is("nav ul.show")) {
            $("nav ul").removeClass("show");
        }
    });

    $(".hamburger").click(function (e) {
        $("nav ul").addClass("show");
        e.stopPropagation();
    });

    if (path_parts().includes("apps")) {
        apps_events();
    }

    if (path_parts().includes('hello')) {
        hello_events();
    }
};


// run this callback when the page is determined to have loaded.
var load = function () {
    // show the .portico-landing when the document is loaded.
    setTimeout(function () {
        $(".portico-landing").addClass("show");
    }, 200);

    // display the `x-grad` element a second after load so that the slide up
    // transition on the .portico-landing is nice and smooth.
    setTimeout(function () {
        $("x-grad").addClass("show");
    }, 1000);

    // Set up events / categories / search
    events();
};

if (document.readyState === "complete") {
    load();
} else {
    $(load);
}

$(function () {
    if (window.location.pathname === '/team/') {
        render_tabs();
    }
});

// Prevent Firefox from bfcaching the page.
// According to https://developer.mozilla.org/en-US/docs/DOM/window.onunload
// Using this event handler in your page prevents Firefox from caching the
// page in the in-memory bfcache (backward/forward cache).
$(window).on('unload', function () {
    $(window).unbind('unload');
});
