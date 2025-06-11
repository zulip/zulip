import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as settings_config from "./settings_config.ts";
import type {StateData} from "./state_data.ts";

export type NavigationView = {
    fragment: string;
    is_pinned: boolean;
    name: string | null;
};

type BuiltInView =
    (typeof settings_config.built_in_views_values)[keyof typeof settings_config.built_in_views_values];

let navigation_views_dict: Map<string, NavigationView>;

export function add_navigation_view(navigation_view: NavigationView): void {
    navigation_views_dict.set(navigation_view.fragment, navigation_view);
}

export function update_navigation_view(fragment: string, data: Partial<NavigationView>): void {
    const existing_view = get_navigation_view_by_fragment(fragment);
    if (existing_view) {
        navigation_views_dict.set(fragment, {
            ...existing_view,
            ...data,
        });
    }
}

export function remove_navigation_view(fragment: string): void {
    navigation_views_dict.delete(fragment);
}

export function get_navigation_view_by_fragment(fragment: string): NavigationView | undefined {
    return navigation_views_dict.get(fragment);
}

export function get_built_in_views(): BuiltInView[] {
    return Object.values(settings_config.built_in_views_values).map((view) => {
        const existing_view = navigation_views_dict.get(view.fragment);
        return {
            ...view,
            is_pinned: existing_view?.is_pinned ?? view.is_pinned,
        };
    });
}

export function get_all_navigation_views(): NavigationView[] {
    const built_in_views = get_built_in_views().map((view) => ({
        fragment: view.fragment,
        is_pinned: view.is_pinned,
        name: view.name,
    }));
    const built_in_fragments = new Set(built_in_views.map((view) => view.fragment));
    const custom_views = [...navigation_views_dict.values()].filter(
        (view) => !built_in_fragments.has(view.fragment),
    );

    return [...built_in_views, ...custom_views];
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
                update_navigation_view(fragment, {is_pinned});
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
                add_navigation_view(new_view);
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
        params.navigation_views.map((view) => [view.fragment, view]),
    );
};
