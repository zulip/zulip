import $ from "jquery";

import {page_params} from "../page_params";

import {detect_user_os} from "./tabbed-instructions";
import render_tabs from "./team";

export function path_parts() {
    return window.location.pathname.split("/").filter((chunk) => chunk !== "");
}

const apps_events = function () {
    const info = {
        windows: {
            alt: "Windows",
            description:
                "Zulip for Windows is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            download_link: "/apps/download/windows",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
        },
        mac: {
            alt: "macOS",
            description:
                "Zulip on macOS is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            download_link: "/apps/download/mac",
            mac_arm64_link: "/apps/download/mac-arm64",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
        },
        android: {
            alt: "Android",
            description: "Zulip's native Android app makes it easy to keep up while on the go.",
            show_instructions: false,
            play_store_link: "https://play.google.com/store/apps/details?id=com.zulipmobile",
            download_link: "https://github.com/zulip/zulip-mobile/releases/latest",
            app_type: "mobile",
        },
        ios: {
            alt: "iOS",
            description: "Zulip's native iOS app makes it easy to keep up while on the go.",
            show_instructions: false,
            app_store_link: "https://itunes.apple.com/us/app/zulip/id1203036395",
            app_type: "mobile",
        },
        linux: {
            alt: "Linux",
            description:
                "Zulip on the Linux desktop is even better than Zulip on the web, with a cleaner look, tray integration, native notifications, and support for multiple Zulip accounts.",
            download_link: "/apps/download/linux",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
        },
    };

    let version;

    function get_version_from_path() {
        let result;
        const parts = path_parts();

        for (const version of Object.keys(info)) {
            if (parts.includes(version)) {
                result = version;
            }
        }

        result = result || detect_user_os();
        return result;
    }

    const update_page = function () {
        const $download_instructions = $(".download-instructions");
        const $third_party_apps = $("#third-party-apps");
        const $download_android_apk = $("#download-android-apk");
        const $download_from_google_play_store = $(".download-from-google-play-store");
        const $download_from_apple_app_store = $(".download-from-apple-app-store");
        const $download_from_microsoft_store = $("#download-from-microsoft-store");
        const $download_mac_arm64 = $("#download-mac-arm64");
        const $desktop_download_link = $(".desktop-download-link");
        const version_info = info[version];

        $(".info .platform").text(version_info.alt);
        $(".info .description").text(version_info.description);
        $desktop_download_link.attr("href", version_info.download_link);
        $download_from_google_play_store.attr("href", version_info.play_store_link);
        $download_from_apple_app_store.attr("href", version_info.app_store_link);
        $download_android_apk.attr("href", version_info.download_link);
        $download_mac_arm64.attr("href", version_info.mac_arm64_link);
        $download_instructions.find("a").attr("href", version_info.install_guide);

        $download_instructions.toggle(version_info.show_instructions);

        $third_party_apps.toggle(version_info.app_type === "desktop");
        $desktop_download_link.toggle(version_info.app_type === "desktop");
        $download_android_apk.toggle(version === "android");
        $download_from_google_play_store.toggle(version === "android");
        $download_from_apple_app_store.toggle(version === "ios");
        $download_from_microsoft_store.toggle(version === "windows");
        $download_mac_arm64.toggle(version === "mac");
    };

    // init
    version = get_version_from_path();
    update_page();
};

const events = function () {
    if (path_parts().includes("apps")) {
        apps_events();
    }
};

$(() => {
    // Set up events / categories / search
    events();

    if (window.location.pathname === "/team/") {
        const contributors = page_params.contributors;
        delete page_params.contributors;
        render_tabs(contributors);
    }

    if (window.location.pathname.endsWith("/plans/")) {
        const tabs = ["#cloud", "#self-hosted"];
        // Show the correct tab based on context.
        let tab_to_show = $(".portico-pricing").hasClass("showing-self-hosted")
            ? "#self-hosted"
            : "#cloud";
        const target_hash = window.location.hash;

        // Capture self-hosted-based fragments, such as
        // #self-hosted-plan-comparison, and show the
        // #self-hosted tab
        if (target_hash.startsWith("#self-hosted")) {
            tab_to_show = "#self-hosted";
        }

        // Don't scroll to tab targets
        if (tabs.includes(target_hash)) {
            window.scroll({top: 0});
        }

        const $pricing_wrapper = $(".portico-pricing");
        $pricing_wrapper.removeClass("showing-cloud showing-self-hosted");
        $pricing_wrapper.addClass(`showing-${tab_to_show.slice(1)}`);

        const $comparison_table = $(".zulip-plans-comparison");

        // Not all pages that show plans include the comparison
        // table, but when it's present, make sure to align the
        // comparison table with the current active plans tab
        if ($comparison_table.length > 0) {
            // Make sure that links coming from elsewhere scroll
            // to the comparison table
            if (target_hash.includes("plan-comparison")) {
                document.querySelector(target_hash).scrollIntoView();
            }
            const plans_columns_count = tab_to_show.slice(1) === "self-hosted" ? 4 : 3;

            // Set the correct values for span and colspan
            $(".features-col-group").attr("span", plans_columns_count);
            $(".subheader-filler").attr("colspan", plans_columns_count);
        }
    }
});

// Scroll to anchor link when clicked. Note that help.js has a similar
// function; this file and help.js are never included on the same
// page.
$(document).on("click", ".markdown h1, .markdown h2, .markdown h3", function () {
    window.location.hash = $(this).attr("id");
});

$(document).on("click", ".pricing-tab", function () {
    const id = $(this).attr("id");
    const $pricing_wrapper = $(".portico-pricing");
    $pricing_wrapper.removeClass("showing-cloud showing-self-hosted");
    $pricing_wrapper.addClass(`showing-${id}`);

    const $comparison_table = $(".zulip-plans-comparison");
    const comparison_table_id = $comparison_table.attr(id);

    // Not all pages that show plans include the comparison
    // table, but when it's present, make sure to set the
    // comparison table features to match the current active tab
    // However, once a user has begun to interact with the
    // comparison table, giving the `id` attribute a value, we
    // no longer apply this logic
    if ($comparison_table.length > 0 && !comparison_table_id) {
        const plans_columns_count = id === "self-hosted" ? 4 : 3;

        // Set the correct values for span and colspan
        $(".features-col-group").attr("span", plans_columns_count);
        $(".subheader-filler").attr("colspan", plans_columns_count);
    }

    history.pushState(null, null, `#${id}`);
});

$(document).on("click", ".comparison-tab", function () {
    const plans_columns_counts = {
        "tab-cloud": 3,
        "tab-hosted": 4,
        "tab-all": 7,
    };

    const tab_label = $(this)[0].dataset.label;
    const plans_columns_count = plans_columns_counts[tab_label];
    const visible_plans_id = `showing-${tab_label}`;

    $(".zulip-plans-comparison").attr("id", visible_plans_id);

    // Set the correct values for span and colspan
    $(".features-col-group").attr("span", plans_columns_count);
    $(".subheader-filler").attr("colspan", plans_columns_count);

    // To accommodate the icons in the All view, we need to attach
    // additional logic to handle the increased subheader-row size.
    if (visible_plans_id === "showing-tab-all") {
        // We need to be aware of user scroll direction
        let previous_y_position = 0;
        // We need to be aware of the y value of the
        // entry record for the IntersectionObserver callback
        // on subheaders of interest (those about to be sticky)
        let previous_entry_y = 0;

        const isScrollingUp = () => {
            let is_scrolling_up = true;
            if (window.scrollY > previous_y_position) {
                is_scrolling_up = false;
            }

            previous_y_position = window.scrollY;

            return is_scrolling_up;
        };

        const observer = new IntersectionObserver(
            ([entries]) => {
                // We want to stop an infinite jiggle when a change in subheader
                // padding erroneously triggers the observer at just the right spot.
                // There may be a momentary jiggle, but it will resolve almost
                // immediately. Rounding to the nearest full pixel is precise enough;
                // full values would cause the jiggle to continue.
                const rounded_entry_y = Math.ceil(entries.boundingClientRect.y);
                if (rounded_entry_y === previous_entry_y) {
                    // Jiggles might end with the class being removed, which
                    // is the poorer behavior, so always make sure the "stuck"
                    // class is present on a jiggling element.
                    entries.target.classList.add("stuck");
                    return;
                }

                // `intersectionRatio` values are 0 when the element first comes into
                // view at the bottom of the page, and then again at the top--which is
                // what we care about. That why we only want to force the class toggle
                // when dealing with subheader elements closer to the top of the page.

                // But: once the "stuck" class has been applied, it can be removed
                // too eagerly should a user scroll back down. So we want to determine
                // whether a user is scrolling up, in which case we want to act below
                // a certain y value. When they scroll down, we want them to scroll
                // down a bit further, and check for a greater-than y value before
                // removing it.
                let force_class_toggle;
                if (isScrollingUp()) {
                    force_class_toggle =
                        entries.intersectionRatio < 1 && entries.boundingClientRect.y > 125;
                } else {
                    force_class_toggle =
                        entries.intersectionRatio < 1 && entries.boundingClientRect.y < 185;
                }

                // Rather than blindly toggle, we force `classList.toggle` to add
                // (which may mean keeping the class on) or remove (keeping it off)
                // depending on scroll direction, etc.
                entries.target.classList.toggle("stuck", force_class_toggle);

                // Track the entry's previous rounded y.
                previous_entry_y = rounded_entry_y;
            },
            // To better catch subtle changes on IntersectionObserver, we use
            // an array of threshold values to detect exits (0) as well as
            // full intersections (1).
            // The -110px rootMargin value is arrived at from 60px worth of
            // navigation menu, and the header-row height minus extra top
            // padding.
            {threshold: [0, 1], rootMargin: "-110px 0px 0px 0px"},
        );

        for (const subheader of document.querySelectorAll("#showing-tab-all td.subheader")) {
            observer.observe(subheader);
        }
    }
});
