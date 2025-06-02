import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as settings_config from "./settings_config.ts";
import type {StateData} from "./state_data.ts";

export type NavigationView = {
    fragment: string;
    is_pinned: boolean;
    name: string | null;
};

let navigation_views_dict: Map<string, NavigationView>;

export function update_navigation_view_dict(navigation_view: NavigationView): void {
    navigation_views_dict.set(navigation_view.fragment, navigation_view);
}

export function remove_navigation_view(fragment: string): void {
    navigation_views_dict.delete(fragment);
}

export function get_navigation_view_by_fragment(fragment: string): NavigationView | undefined {
    const navigation_view = navigation_views_dict.get(fragment);
    if (navigation_view === undefined) {
        return undefined;
    }
    return navigation_view;
}

export function get_all_built_in_navigation_views(): NavigationView[] {
    const built_in_views = Object.values(settings_config.built_in_navigation_view_values);
    return built_in_views.map((view) => ({
        fragment: view.fragment,
        is_pinned: true,
        name: view.name,
    }));
}

export function get_all_navigation_views(): NavigationView[] {
    const built_in_views = get_all_built_in_navigation_views();
    const navigation_views: NavigationView[] = [];
    for (const view of built_in_views) {
        if (navigation_views_dict.has(view.fragment)) {
            const existing_view = get_navigation_view_by_fragment(view.fragment);
            assert(existing_view !== undefined);
            view.is_pinned = existing_view.is_pinned;
            update_navigation_view_dict(view);
            continue;
        }
        navigation_views.push(view);
    }
    navigation_views.push(...navigation_views_dict.values());
    return navigation_views;
}

export function set_view_pinned_status(
    fragment: string,
    is_pinned: boolean,
    success_callback?: () => void,
    error_callback?: () => void,
): void {
    const existing_view = get_navigation_view_by_fragment(fragment);
    
    if (existing_view) {
        void channel.patch({
            url: `/json/navigation_views/${encodeURIComponent(fragment)}`,
            data: {is_pinned},
            success() {
                existing_view.is_pinned = is_pinned;
                update_navigation_view_dict(existing_view);
                success_callback?.();
            },
            error() {
                blueslip.error("Failed to update navigation view", {fragment, is_pinned});
                error_callback?.();
            },
        });
    } else {
        void channel.post({
            url: "/json/navigation_views",
            data: {
                fragment,
                is_pinned,
            },
            success() {
                const new_view: NavigationView = {
                    fragment,
                    is_pinned,
                    name: null,
                };
                update_navigation_view_dict(new_view);
                success_callback?.();
            },
            error() {
                blueslip.error("Failed to create navigation view", {fragment, is_pinned});
                error_callback?.();
            },
        });
    }
}

export function delete_navigation_view(
    fragment: string,
    success_callback?: () => void,
    error_callback?: () => void,
): void {
    void channel.del({
        url: `/json/navigation_views/${encodeURIComponent(fragment)}`,
        success() {
            remove_navigation_view(fragment);
            success_callback?.();
        },
        error() {
            blueslip.error("Failed to delete navigation view", {fragment});
            error_callback?.();
        },
    });
}

export const initialize = (params: StateData["navigation_views"]): void => {
    navigation_views_dict = new Map<string, NavigationView>(
        params.navigation_views.map((view) => [view.fragment, {
            fragment: view.fragment,
            is_pinned: view.is_pinned,
            name: view.name ?? null,
        }]),
    );
};
