import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {page_params} from "../base_page_params.ts";
import * as blueslip from "../blueslip.ts";
import * as util from "../util.ts";

import { trackMacArchDetection, trackMacDownloadClicked } from "./google-analytics.ts";
import { type ArchitectureInfo, MacArchitectureDetector } from "./mac-architecture-detector.ts";
import type {UserOS} from "./tabbed-instructions.ts";
import {detect_user_os} from "./tabbed-instructions.ts";
import render_tabs from "./team.ts";

type VersionInfo = {
    description: string;
    app_type: "mobile" | "desktop";
} & (
    | {
          alt: "Windows";
          download_link: string;
          install_guide: string;
      }
    | {
          alt: "macOS";
          download_link: string;
          mac_intel_link: string;
          install_guide: string;
      }
    | {
          alt: "Android";
          download_link: string;
          play_store_link: string;
          legacy_download_link: string;
      }
    | {
          alt: "iOS";
          app_store_link: string;
      }
    | {
          alt: "Linux";
          download_link: string;
          install_guide: string;
      }
) &
    (
        | {
              show_instructions: false;
              download_instructions?: undefined;
          }
        | {
              show_instructions: true;
              download_instructions: string;
          }
    );

export function path_parts(): string[] {
    return window.location.pathname.split("/").filter((chunk) => chunk !== "");
}

const apps_events = function (): void {
    const info: Record<UserOS, VersionInfo> = {
        windows: {
            alt: "Windows",
            description:
                "The Zulip desktop app comes with native <a class='apps-page-link' href='/help/desktop-notifications'>desktop notifications</a>, support for multiple Zulip accounts, and a dedicated tray icon.",
            download_link: "/apps/download/windows",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
            download_instructions:
                'For help or to install offline, see our <a class="apps-page-link" href="/help/desktop-app-install-guide" target="_blank" rel="noopener noreferrer">installation guide</a>.',
        },
        mac: {
            alt: "macOS",
            description:
                "The Zulip desktop app comes with native <a class='apps-page-link' href='/help/desktop-notifications'>desktop notifications</a>, support for multiple Zulip accounts, and a dedicated tray icon.",
            download_link: "/apps/download/mac-arm64",
            mac_intel_link: "/apps/download/mac-intel",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
            download_instructions:
                'For help or to install via Homebrew, see our <a class="apps-page-link" href="/help/desktop-app-install-guide" target="_blank" rel="noopener noreferrer">installation guide</a>.',
        },
        android: {
            alt: "Android",
            description:
                "Zulip's native Android app makes it easy to keep up while on the go, with fully customizable <a class='apps-page-link' href='/help/mobile-notifications'>mobile notifications</a>.",
            show_instructions: false,
            play_store_link: "https://play.google.com/store/apps/details?id=com.zulipmobile",
            download_link: "https://github.com/zulip/zulip-flutter/releases/latest",
            legacy_download_link: "https://github.com/zulip/zulip-mobile/releases/latest",
            app_type: "mobile",
        },
        ios: {
            alt: "iOS",
            description:
                "Zulip's native iOS app makes it easy to keep up while on the go, with fully customizable <a class='apps-page-link' href='/help/mobile-notifications'>mobile notifications</a>.",
            show_instructions: false,
            app_store_link: "https://itunes.apple.com/us/app/zulip/id1203036395",
            app_type: "mobile",
        },
        linux: {
            alt: "Linux",
            description:
                "The Zulip desktop app comes with native <a class='apps-page-link' href='/help/desktop-notifications'>desktop notifications</a>, support for multiple Zulip accounts, and a dedicated tray icon.",
            download_link: "/apps/download/linux",
            show_instructions: true,
            install_guide: "/help/desktop-app-install-guide",
            app_type: "desktop",
            download_instructions:
                'For help or to install via a package manager, see our <a class="apps-page-link" href="/help/desktop-app-install-guide" target="_blank" rel="noopener noreferrer">installation guide</a>.',
        },
    };

    let version: UserOS;

    function get_version_from_path(): UserOS {
        let result: UserOS | undefined;
        const parts = path_parts();
        let version: UserOS;
        for (version in info) {
            if (parts.includes(version)) {
                result = version;
            }
        }

        result = result ?? detect_user_os();
        return result;
    }

    const update_page: () => void = function () {
        const $download_instructions = $(".download-instructions");
        const $third_party_apps = $("#third-party-apps");
        const $download_android_apk = $("#download-android-apk");
        const $android_apk_current = $(".android-apk-current");
        const $android_apk_legacy = $(".android-apk-legacy");
        const $download_from_google_play_store = $(".download-from-google-play-store");
        const $download_from_apple_app_store = $(".download-from-apple-app-store");
        const $download_from_microsoft_store = $("#download-from-microsoft-store");
        const $download_mac_intel = $("#download-mac-intel");
        const $desktop_download_link = $(".desktop-download-link");
        const version_info = info[version];

        $(".info .platform").text(version_info.alt);
        $(".info .description").html(version_info.description);

        if (version_info.alt === "Android") {
            $download_from_google_play_store.attr("href", version_info.play_store_link);
            $android_apk_current.attr("href", version_info.download_link);
            $android_apk_legacy.attr("href", version_info.legacy_download_link);
        } else if (version_info.alt === "iOS") {
            $download_from_apple_app_store.attr("href", version_info.app_store_link);
        } else {
            $desktop_download_link.attr("href", version_info.download_link);
            if (version_info.alt === "macOS") {
                $download_mac_intel.find("a").attr("href", version_info.mac_intel_link);
            }
            assert(version_info.download_instructions);
            $download_instructions.html(version_info.download_instructions);
        }

        $download_instructions.toggle(version_info.show_instructions);

        $third_party_apps.toggle(version_info.app_type === "desktop");
        $desktop_download_link.toggle(version_info.app_type === "desktop");
        $download_android_apk.toggle(version === "android");
        $download_from_google_play_store.toggle(version === "android");
        $download_from_apple_app_store.toggle(version === "ios");
        $download_from_microsoft_store.toggle(version === "windows");
        $download_mac_intel.toggle(version === "mac");

    const shouldDetectArch = MacArchitectureDetector !== undefined && version === 'mac';
        if (shouldDetectArch) {
            const $primary = $('.download-mac-primary');
            const $secondary = $('.download-mac-secondary');

            // Show loading state
            $primary.addClass('detecting-arch').prop('disabled', true);

            void (async (): Promise<void> => {
                try {
                    const detector = MacArchitectureDetector.getInstance();
                    const info: ArchitectureInfo = await detector.detectArchitecture();

                    // Remove loading state
                    $primary.removeClass('detecting-arch').prop('disabled', false);

                    if (info.isAppleSilicon === null) {
                        trackMacArchDetection('unknown', info.confidence, 'unknown');
                        return;
                    }

                    if (!info.isAppleSilicon && info.confidence === 'high') {
                        $primary.attr('href', '/apps/download/mac-intel');
                        $primary.find('.button-text').text('Download for macOS (Intel)');
                        $primary.attr('data-mac-arch', 'intel');

                        $secondary.attr('href', '/apps/download/mac-arm64');
                        $secondary.text('or download Apple Silicon build');
                        $secondary.attr('data-mac-arch', 'arm64');

                        $('.mac-download-warning').hide();
                        trackMacArchDetection('Intel', info.confidence, 'user_agent_data');
                    } else if (info.isAppleSilicon) {
                        if (info.confidence === 'high') {
                            const $text = $primary.find('.button-text');
                            const $badge = $('<span>').addClass('recommended-badge').text(' ✓ Recommended');
                            $text.append($badge);
                        }
                        $primary.attr('data-mac-arch', 'arm64');
                        $secondary.attr('data-mac-arch', 'intel');
                        trackMacArchDetection('Apple Silicon', info.confidence, info.confidence === 'high' ? 'user_agent_data' : 'webgl');
                    }

                    $primary.attr('data-detected-arch', detector.getArchitectureName(info));
                    $primary.attr('data-confidence', info.confidence);

                } catch (error) {
                    // Remove loading state and surface error
                    $('.download-mac-primary').removeClass('detecting-arch').prop('disabled', false);
                    blueslip.error('Mac architecture detection failed', {error: String(error)});
                    trackMacArchDetection('error', 'unknown', 'error');
                }
            })();

            // Click tracking for downloads
            $(document).on('click', '.download-mac-primary, .download-mac-secondary', function () {
                const arch = $(this).attr('data-mac-arch') ?? 'unknown';
                try {
                    trackMacDownloadClicked(arch);
                } catch {
                    // ignore analytics failures
                }
            });
        }
    };

    version = get_version_from_path();
    update_page();
};

const events = function (): void {
    if (path_parts().includes("apps")) {
        apps_events();
    }
};

$(() => {

    events();

    if (window.location.pathname === "/team/") {
        assert(page_params.page_type === "team");
        assert(page_params.contributors);
        const contributors = page_params.contributors;
        delete page_params.contributors;
        render_tabs(contributors);
    }

    if (window.location.pathname.endsWith("/plans/")) {
        const tabs = ["#cloud", "#self-hosted"];

        let tab_to_show = $(".portico-pricing").hasClass("showing-self-hosted")
            ? "#self-hosted"
            : "#cloud";
    const target_hash = window.location.hash;
        if (target_hash.startsWith("#self-hosted")) {
            tab_to_show = "#self-hosted";
        }


        if (tabs.includes(target_hash)) {
            window.scroll({top: 0});
        }

        const $pricing_wrapper = $(".portico-pricing");
        $pricing_wrapper.removeClass("showing-cloud showing-self-hosted");
        $pricing_wrapper.addClass(`showing-${tab_to_show.slice(1)}`);

        if (target_hash.includes("plan-comparison")) {
            document.querySelector(target_hash)!.scrollIntoView();
        }

        const plans_columns_count = tab_to_show.slice(1) === "self-hosted" ? 4 : 3;

        $(".features-col-group").attr("span", plans_columns_count);
        $(".subheader-filler").attr("colspan", plans_columns_count);
    }

    if (window.location.pathname.endsWith("/features/")) {

        $(".features-col-group").attr("span", 3);
        $(".subheader-filler").attr("colspan", 3);
    }
});


$(document).on("click", ".markdown h1, .markdown h2, .markdown h3", function () {
    window.location.hash = $(this).attr("id")!;
});

$(document).on("click", ".nav-zulip-logo", (e) => {
    if (document.querySelector(".portico-hello-page")) {
        e.preventDefault();
        window.scrollTo({top: 0, behavior: "smooth"});
    }
});

$(document).on("click", ".pricing-tab", function () {
    const id = $(this).attr("id")!;
    const $pricing_wrapper = $(".portico-pricing");
    $pricing_wrapper.removeClass("showing-cloud showing-self-hosted");
    $pricing_wrapper.addClass(`showing-${id}`);

    const $comparison_table = $(".zulip-plans-comparison");
    const comparison_table_id = $comparison_table.attr(id);


    if ($comparison_table.length > 0 && !comparison_table_id) {
        const plans_columns_count = id === "self-hosted" ? 4 : 3;

        $(".features-col-group").attr("span", plans_columns_count);
        $(".subheader-filler").attr("colspan", plans_columns_count);
    }

    window.history.pushState(null, "", `#${id}`);
});

$(document).on("click", ".comparison-tab", function (this: HTMLElement, _event: JQuery.Event) {
    const plans_columns_counts = {
        "tab-cloud": 3,
        "tab-hosted": 4,
        "tab-all": 7,
    };

    const tab_label = z
        .enum(["tab-cloud", "tab-hosted", "tab-all"])
        .parse(util.the($(this)).dataset.label);
    const plans_columns_count = plans_columns_counts[tab_label];
    const visible_plans_id = `showing-${tab_label}`;

    $(".zulip-plans-comparison").attr("id", visible_plans_id);


    $(".features-col-group").attr("span", plans_columns_count);
    $(".subheader-filler").attr("colspan", plans_columns_count);

    if (visible_plans_id === "showing-tab-all") {

        let previous_y_position = 0;

        let previous_entry_y = 0;

        const isScrollingUp = (): boolean => {
            let is_scrolling_up = true;
            if (window.scrollY > previous_y_position) {
                is_scrolling_up = false;
            }

            previous_y_position = window.scrollY;

            return is_scrolling_up;
        };

        const observer = new IntersectionObserver(
            ([entries]) => {
                assert(entries !== undefined);

                const rounded_entry_y = Math.ceil(entries.boundingClientRect.y);
                if (rounded_entry_y === previous_entry_y) {

                    entries.target.classList.add("stuck");
                    return;
                }


                let force_class_toggle;
                if (isScrollingUp()) {
                    force_class_toggle =
                        entries.intersectionRatio < 1 && entries.boundingClientRect.y > 125;
                } else {
                    force_class_toggle =
                        entries.intersectionRatio < 1 && entries.boundingClientRect.y < 185;
                }

                entries.target.classList.toggle("stuck", force_class_toggle);

                previous_entry_y = rounded_entry_y;
            },
  
            {threshold: [0, 1], rootMargin: "-110px 0px 0px 0px"},
        );

        for (const subheader of document.querySelectorAll("#showing-tab-all td.subheader")) {
            observer.observe(subheader);
        }
    }
});
