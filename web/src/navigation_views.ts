import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";
import type {NavigationView, StateData} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

export type BuiltInViewBasicMetadata = {
    fragment: string;
    name: string;
    is_pinned: boolean;
    icon: string;
    css_class_suffix: string;
    tooltip_template_id: string;
    has_unread_count: boolean;
    unread_count_type: "normal-count" | "quiet-count" | "";
    supports_masked_unread: boolean;
    hidden_for_spectators: boolean;
    menu_icon_class: string;
    menu_aria_label: string;
    home_view_code: string;
    prioritize_in_condensed_view: boolean;
};

export const built_in_views_meta_data: Record<string, BuiltInViewBasicMetadata> = {
    inbox: {
        fragment: "inbox",
        name: $t({defaultMessage: "Inbox"}),
        is_pinned: true,
        icon: "zulip-icon-inbox",
        css_class_suffix: "inbox",
        tooltip_template_id: "inbox-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: true,
        hidden_for_spectators: true,
        menu_icon_class: "inbox-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Inbox options"}),
        home_view_code: "inbox",
        prioritize_in_condensed_view: true,
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
        supports_masked_unread: true,
        hidden_for_spectators: false,
        menu_icon_class: "recent-view-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Recent conversations options"}),
        home_view_code: "recent_topics",
        prioritize_in_condensed_view: true,
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
        supports_masked_unread: true,
        hidden_for_spectators: false,
        menu_icon_class: "all-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Combined feed options"}),
        home_view_code: "all_messages",
        prioritize_in_condensed_view: true,
    },
    mentions: {
        fragment: "narrow/is/mentioned",
        name: $t({defaultMessage: "Mentions"}),
        is_pinned: true,
        icon: "zulip-icon-at-sign",
        css_class_suffix: "mentions",
        tooltip_template_id: "mentions-tooltip-template",
        has_unread_count: true,
        unread_count_type: "normal-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: true,
    },
    my_reactions: {
        fragment: "narrow/has/reaction/sender/me",
        name: $t({defaultMessage: "Reactions"}),
        is_pinned: true,
        icon: "zulip-icon-smile",
        css_class_suffix: "my_reactions",
        tooltip_template_id: "my-reactions-tooltip-template",
        has_unread_count: false,
        unread_count_type: "",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
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
        supports_masked_unread: true,
        hidden_for_spectators: true,
        menu_icon_class: "starred-messages-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Starred messages options"}),
        home_view_code: "",
        prioritize_in_condensed_view: true,
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
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "drafts-sidebar-menu-icon",
        menu_aria_label: $t({defaultMessage: "Drafts options"}),
        home_view_code: "",
        prioritize_in_condensed_view: false,
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
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
    reminders: {
        fragment: "reminders",
        name: $t({defaultMessage: "Reminders"}),
        is_pinned: true,
        icon: "zulip-icon-alarm-clock",
        css_class_suffix: "reminders",
        tooltip_template_id: "reminders-tooltip-template",
        has_unread_count: true,
        unread_count_type: "quiet-count",
        supports_masked_unread: false,
        hidden_for_spectators: true,
        menu_icon_class: "",
        menu_aria_label: "",
        home_view_code: "",
        prioritize_in_condensed_view: false,
    },
};

let navigation_views_dict: Map<string, NavigationView>;

export function add_navigation_view(navigation_view: NavigationView): void {
    navigation_views_dict.set(navigation_view.fragment, navigation_view);
}

export function update_navigation_view(fragment: string, data: Partial<NavigationView>): void {
    const view = get_navigation_view_by_fragment(fragment);
    if (view) {
        navigation_views_dict.set(fragment, {
            ...view,
            ...data,
        });
    } else {
        blueslip.error("Cannot find navigation view to update");
    }
}

export function remove_navigation_view(fragment: string): void {
    navigation_views_dict.delete(fragment);
}

export function get_navigation_view_by_fragment(fragment: string): NavigationView | undefined {
    return navigation_views_dict.get(fragment);
}

export type BuiltInViewMetadata = BuiltInViewBasicMetadata & {
    is_home_view: boolean;
    unread_count?: number;
};

export function get_built_in_views(): BuiltInViewMetadata[] {
    return Object.values(built_in_views_meta_data).map((view) => {
        const view_current_data = get_navigation_view_by_fragment(view.fragment);
        return {
            ...view,
            is_pinned: view_current_data?.is_pinned ?? view.is_pinned,
            is_home_view: view.home_view_code === user_settings.web_home_view,
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

export const initialize = (params: StateData["navigation_views"]): void => {
    navigation_views_dict = new Map<string, NavigationView>(
        params.navigation_views.map((view) => [view.fragment, view]),
    );
};
