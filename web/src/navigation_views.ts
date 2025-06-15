import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import type {StateData} from "./state_data.ts";

export const built_in_views_values = {
    inbox: {
        fragment: "inbox",
        name: $t({defaultMessage: "Inbox"}),
        is_pinned: true,
        icon: "zulip-icon-inbox",
        css_class_suffix: "inbox",
        tooltip_template_id: "inbox-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        hidden_for_spectators: true,
        menu_icon_class: "inbox-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Inbox options"}),
        home_view_code: "inbox",
    },
    recent_view: {
        fragment: "recent",
        name: $t({defaultMessage: "Recent conversations"}),
        is_pinned: true,
        icon: "zulip-icon-recent",
        css_class_suffix: "recent_view",
        tooltip_template_id: "recent-conversations-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        hidden_for_spectators: false,
        menu_icon_class: "recent-view-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Recent conversations options"}),
        home_view_code: "recent_topics",
    },
    all_messages: {
        fragment: "feed",
        name: $t({defaultMessage: "Combined feed"}),
        is_pinned: true,
        icon: "zulip-icon-all-messages",
        css_class_suffix: "all_messages",
        tooltip_template_id: "all-message-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        hidden_for_spectators: false,
        menu_icon_class: "all-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Combined feed options"}),
        home_view_code: "all_messages",
        additional_link_class: "home-link",
    },
    mentions: {
        fragment: "narrow/is/mentioned",
        name: $t({defaultMessage: "Mentions"}),
        is_pinned: true,
        icon: "zulip-icon-at-sign",
        css_class_suffix: "mentions",
        tooltip_template_id: "mentions-tooltip-template",
        has_unread_count: true,
        unread_count_type: "",
        hidden_for_spectators: true,
        menu_icon_class: "mentions-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Mentions options"}),
        home_view_code: null,
    },
    my_reactions: {
        fragment: "narrow/has/reaction/sender/me",
        name: $t({defaultMessage: "Reactions"}),
        is_pinned: true,
        icon: "zulip-icon-smile",
        css_class_suffix: "my_reactions",
        tooltip_template_id: "my-reactions-tooltip-template",
        has_unread_count: true,
        unread_count_type: "",
        hidden_for_spectators: true,
        menu_icon_class: "reactions-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Reactions options"}),
        home_view_code: null,
    },
    starred_messages: {
        fragment: "narrow/is/starred",
        name: $t({defaultMessage: "Starred messages"}),
        is_pinned: true,
        icon: "zulip-icon-star",
        css_class_suffix: "starred_messages",
        tooltip_template_id: "starred-message-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        hidden_for_spectators: true,
        menu_icon_class: "starred-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Starred messages options"}),
        has_masked_unread: true,
        home_view_code: null,
    },
    drafts: {
        fragment: "drafts",
        name: $t({defaultMessage: "Drafts"}),
        is_pinned: true,
        icon: "zulip-icon-drafts",
        css_class_suffix: "drafts",
        tooltip_template_id: "drafts-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        hidden_for_spectators: true,
        menu_icon_class: "drafts-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Drafts options"}),
        home_view_code: null,
    },
    scheduled_messages: {
        fragment: "scheduled",
        name: $t({defaultMessage: "Scheduled messages"}),
        is_pinned: true,
        icon: "zulip-icon-calendar-days",
        css_class_suffix: "scheduled_messages",
        tooltip_template_id: "scheduled-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        menu_icon_class: "scheduled_messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Scheduled messages options"}),
        hidden_for_spectators: true,
        home_view_code: null,
    },
};

export type NavigationView = {
    fragment: string;
    is_pinned: boolean;
    name: string | null;
};

type BuiltInView = (typeof built_in_views_values)[keyof typeof built_in_views_values];

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
    return Object.values(built_in_views_values).map((view) => {
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
