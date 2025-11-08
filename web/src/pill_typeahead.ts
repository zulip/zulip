import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import {Typeahead} from "./bootstrap_typeahead.ts";
import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as stream_pill from "./stream_pill.ts";
import type {StreamPillData, StreamPillWidget} from "./stream_pill.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import type {CombinedPillContainer, GroupSettingPillContainer} from "./typeahead_helper.ts";
import * as user_group_pill from "./user_group_pill.ts";
import type {UserGroupPillData} from "./user_group_pill.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";
import type {UserPillData, UserPillWidget} from "./user_pill.ts";

function person_matcher(query: string, item: UserPillData): boolean {
    return (
        people.is_known_user_id(item.user.user_id) &&
        typeahead_helper.query_matches_person(query, item)
    );
}

function group_matcher(query: string, item: UserGroupPillData): boolean {
    return typeahead_helper.query_matches_group_name(query, item);
}

type TypeaheadItem = UserGroupPillData | StreamPillData | UserPillData;
type GroupSettingTypeaheadItem = UserGroupPillData | UserPillData;

export function set_up_user(
    $input: JQuery,
    pills: UserPillWidget,
    opts: {
        exclude_bots?: boolean;
        update_func?: () => void;
    },
): void {
    const exclude_bots = opts.exclude_bots;
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };
    new Typeahead(bootstrap_typeahead_input, {
        dropup: true,
        source(_query: string): UserPillData[] {
            return user_pill.typeahead_source(pills, exclude_bots);
        },
        item_html(item: UserPillData, _query: string): string {
            return typeahead_helper.render_person(item);
        },
        matcher(item: UserPillData, query: string): boolean {
            query = query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");
            return person_matcher(query, item);
        },
        sorter(matches: UserPillData[], query: string): UserPillData[] {
            const users = matches.filter((match) => people.is_known_user_id(match.user.user_id));
            return typeahead_helper.sort_recipients({users, query}).map((item) => {
                assert(item.type === "user");
                return item;
            });
        },
        updater(item: UserPillData, _query: string): undefined {
            if (people.is_known_user_id(item.user.user_id)) {
                user_pill.append_user(item.user, pills);
            }
            $input.trigger("focus");
            opts.update_func?.();
        },
        stopAdvance: true,
    });
}

export function set_up_stream(
    $input: JQuery,
    pills: StreamPillWidget,
    opts: {
        help_on_empty_strings?: boolean;
        hide_on_empty_after_backspace?: boolean;
        invite_streams?: boolean;
        update_func?: () => void;
    },
): void {
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };
    opts.help_on_empty_strings ??= false;
    opts.hide_on_empty_after_backspace ??= false;
    new Typeahead(bootstrap_typeahead_input, {
        dropup: true,
        helpOnEmptyStrings: opts.help_on_empty_strings,
        hideOnEmptyAfterBackspace: opts.hide_on_empty_after_backspace,
        source(_query: string): StreamPillData[] {
            return stream_pill.typeahead_source(pills, opts.invite_streams);
        },
        item_html(item: StreamPillData, _query: string): string {
            return typeahead_helper.render_stream(item);
        },
        matcher(item: StreamPillData, query: string): boolean {
            query = query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");
            query = query.trim();
            if (query.startsWith("#")) {
                query = query.slice(1);
            }
            return item.name.toLowerCase().includes(query);
        },
        sorter(matches: StreamPillData[], query: string): StreamPillData[] {
            const stream_matches: StreamPillData[] = [];
            for (const match of matches) {
                assert(match.type === "stream");
                stream_matches.push(match);
            }
            query = query.trim();
            if (query.startsWith("#")) {
                query = query.slice(1);
            }
            return typeahead_helper.sort_streams_by_name(stream_matches, query);
        },
        updater(item: StreamPillData, _query: string): undefined {
            stream_pill.append_stream(item, pills, false);
            $input.trigger("focus");
            opts.update_func?.();
        },
        stopAdvance: true,
    });
}

export function set_up_user_group(
    $input: JQuery,
    pills: user_group_pill.UserGroupPillWidget,
    opts: {
        user_group_source: () => UserGroup[];
    },
): void {
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };
    new Typeahead(bootstrap_typeahead_input, {
        dropup: true,
        source(_query: string): UserGroupPillData[] {
            return opts
                .user_group_source()
                .map((user_group) => ({type: "user_group", ...user_group}));
        },
        item_html(item: UserGroupPillData, _query: string): string {
            return typeahead_helper.render_user_group(item);
        },
        matcher(item: UserGroupPillData, query: string): boolean {
            query = query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");
            return group_matcher(query, item);
        },
        sorter(matches: UserGroupPillData[], query: string): UserGroupPillData[] {
            return typeahead_helper.sort_user_groups(matches, query);
        },
        updater(item: UserGroupPillData, _query: string): undefined {
            user_group_pill.append_user_group(item, pills);
            $input.trigger("focus");
        },
        stopAdvance: true,
        helpOnEmptyStrings: true,
        hideOnEmptyAfterBackspace: true,
    });
}

export function set_up_group_setting_typeahead(
    $input: JQuery,
    pills: GroupSettingPillContainer,
    opts: {
        setting_name: string;
        setting_type: "realm" | "stream" | "group";
        group?: UserGroup | undefined;
    },
): void {
    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };
    new Typeahead(bootstrap_typeahead_input, {
        dropup: true,
        source(_query: string): GroupSettingTypeaheadItem[] {
            let source: GroupSettingTypeaheadItem[] = [];

            source = user_group_pill.typeahead_source(pills, opts.setting_name, opts.setting_type);
            source = [
                ...source,
                ...user_pill.typeahead_source(pills, true, opts.setting_name, opts.setting_type),
            ];

            return source;
        },
        item_html(item: GroupSettingTypeaheadItem, _query: string): string {
            if (item.type === "user_group") {
                return typeahead_helper.render_user_group(item);
            }

            assert(item.type === "user");
            return typeahead_helper.render_person(item);
        },
        matcher(item: GroupSettingTypeaheadItem, query: string): boolean {
            query = query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");

            let matches = false;
            if (item.type === "user_group") {
                matches = matches || group_matcher(query, item);
            }

            if (item.type === "user") {
                matches = matches || person_matcher(query, item);
            }
            return matches;
        },
        sorter(matches: GroupSettingTypeaheadItem[], query: string): GroupSettingTypeaheadItem[] {
            const users: UserPillData[] = [];
            for (const match of matches) {
                if (match.type === "user" && people.is_known_user_id(match.user.user_id)) {
                    users.push(match);
                }
            }

            const groups: UserGroupPillData[] = [];
            for (const match of matches) {
                if (match.type === "user_group") {
                    groups.push(match);
                }
            }

            return typeahead_helper.sort_group_setting_options({
                users,
                query,
                groups,
                target_group: opts.group,
            });
        },
        updater(item: GroupSettingTypeaheadItem, _query: string): undefined {
            if (item.type === "user_group") {
                user_group_pill.append_user_group(item, pills);
            } else if (item.type === "user" && people.is_known_user_id(item.user.user_id)) {
                user_pill.append_user(item.user, pills);
            }

            $input.trigger("focus");
        },
        stopAdvance: true,
        helpOnEmptyStrings: true,
        hideOnEmptyAfterBackspace: true,
    });
}

export function set_up_combined(
    $input: JQuery,
    pills: CombinedPillContainer,
    opts: {
        user: boolean;
        user_group?: boolean;
        stream?: boolean;
        user_source?: () => User[];
        user_group_source?: () => UserGroup[];
        exclude_bots?: boolean;
        update_func?: () => void;
        for_stream_subscribers: boolean;
    },
): void {
    if (!opts.user && !opts.user_group && !opts.stream) {
        blueslip.error("Unspecified possible item types");
        return;
    }
    const include_streams = (query: string): boolean =>
        opts.stream !== undefined && query.trim().startsWith("#");
    const include_user_groups = opts.user_group;
    const include_users = opts.user;
    const exclude_bots = opts.exclude_bots;

    const bootstrap_typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };
    new Typeahead(bootstrap_typeahead_input, {
        dropup: true,
        helpOnEmptyStrings: true,
        hideOnEmptyAfterBackspace: true,
        source(query: string): TypeaheadItem[] {
            let source: TypeaheadItem[] = [];
            if (include_streams(query)) {
                // If query starts with # we expect,
                // only stream suggestions so we simply
                // return stream source.
                return stream_pill.typeahead_source(pills);
            }

            if (include_user_groups) {
                if (opts.user_group_source !== undefined) {
                    const groups: UserGroupPillData[] = opts
                        .user_group_source()
                        .map((user_group) => ({type: "user_group", ...user_group}));
                    source = [...source, ...groups];
                } else {
                    source = [...source, ...user_group_pill.typeahead_source(pills)];
                }
            }

            if (include_users) {
                if (opts.user_source !== undefined) {
                    // If user_source is specified in opts, it
                    // is given priority. Otherwise we use
                    // default user_pill.typeahead_source.
                    const users: UserPillData[] = opts
                        .user_source()
                        .map((user) => ({type: "user", user}));
                    source = [...source, ...users];
                } else {
                    source = [...source, ...user_pill.typeahead_source(pills, exclude_bots)];
                }
            }
            return source;
        },
        item_html(item: TypeaheadItem, query: string): string {
            if (include_streams(query) && item.type === "stream") {
                return typeahead_helper.render_stream(item);
            }

            if (include_user_groups && item.type === "user_group") {
                return typeahead_helper.render_user_group(item);
            }

            // After reaching this point, it is sure
            // that given item is a person. So this
            // handles `include_users` cases along with
            // default cases.
            assert(item.type === "user");
            return typeahead_helper.render_person(item);
        },
        matcher(item: TypeaheadItem, query: string): boolean {
            query = query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");

            if (include_streams(query) && item.type === "stream") {
                query = query.trim().slice(1);
                return item.name.toLowerCase().includes(query);
            }

            let matches = false;
            if (include_user_groups && item.type === "user_group") {
                matches = matches || group_matcher(query, item);
            }

            if (include_users && item.type === "user") {
                matches = matches || person_matcher(query, item);
            }
            return matches;
        },
        sorter(matches: TypeaheadItem[], query: string): TypeaheadItem[] {
            if (include_streams(query)) {
                const stream_matches: StreamPillData[] = [];
                for (const match of matches) {
                    assert(match.type === "stream");
                    stream_matches.push(match);
                }
                return typeahead_helper.sort_streams(stream_matches, query.trim().slice(1));
            }

            const users: UserPillData[] = [];
            if (include_users) {
                for (const match of matches) {
                    if (match.type === "user" && people.is_known_user_id(match.user.user_id)) {
                        users.push(match);
                    }
                }
            }

            const groups: UserGroupPillData[] = [];
            if (include_user_groups) {
                for (const match of matches) {
                    if (match.type === "user_group") {
                        groups.push(match);
                    }
                }
            }

            return typeahead_helper.sort_stream_or_group_members_options({
                users,
                query,
                groups,
                for_stream_subscribers: opts.for_stream_subscribers,
            });
        },
        updater(item: TypeaheadItem, query: string): undefined {
            if (include_streams(query) && item.type === "stream") {
                stream_pill.append_stream(item, pills);
            } else if (include_user_groups && item.type === "user_group") {
                const show_expand_button =
                    !opts.for_stream_subscribers &&
                    (item.members.size > 0 || item.direct_subgroup_ids.size > 0);
                user_group_pill.append_user_group(item, pills, true, show_expand_button);
            } else if (
                include_users &&
                item.type === "user" &&
                people.is_known_user_id(item.user.user_id)
            ) {
                user_pill.append_user(item.user, pills);
            }

            $input.trigger("focus");
            if (opts.update_func) {
                opts.update_func();
            }
        },
        stopAdvance: true,
    });
}
