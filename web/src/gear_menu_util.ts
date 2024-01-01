import {$t} from "./i18n";
import {state_data} from "./state_data";

export function version_display_string(): string {
    const version = state_data.zulip_version;
    const is_fork = state_data.zulip_merge_base && state_data.zulip_merge_base !== version;

    if (state_data.zulip_version.endsWith("-dev+git")) {
        // The development environment uses this version string format.
        return $t({defaultMessage: "Zulip Server dev environment"});
    }

    if (is_fork) {
        // For forks, we want to describe the Zulip version this was
        // forked from, and that it was modified.
        const display_version = state_data.zulip_merge_base
            .replace(/\+git.*/, "")
            .replace(/(-beta\d+).*/, "$1")
            .replace(/-dev.*/, "-dev");
        return $t({defaultMessage: "Zulip Server {display_version} (modified)"}, {display_version});
    }

    // The below cases are all for official versions; either a
    // release, or Git commit from one of Zulip's official branches.

    if (version.includes("+git")) {
        // A version from a Zulip official maintenance branch such as 5.x.
        const display_version = version.replace(/\+git.*/, "");
        return $t({defaultMessage: "Zulip Server {display_version} (patched)"}, {display_version});
    }

    const display_version = version.replace(/\+git.*/, "").replace(/-dev.*/, "-dev");
    return $t({defaultMessage: "Zulip Server {display_version}"}, {display_version});
}
