import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import {Typeahead} from "./bootstrap_typeahead";
import type {TypeaheadInputElement} from "./bootstrap_typeahead";
import * as people from "./people";
import type {User} from "./people";
import * as stream_pill from "./stream_pill";
import type {StreamPillData} from "./stream_pill";
import * as typeahead_helper from "./typeahead_helper";
import type {CombinedPillContainer} from "./typeahead_helper";
import * as user_group_pill from "./user_group_pill";
import type {UserGroupPillData} from "./user_group_pill";
import type {UserGroup} from "./user_groups";
import * as user_pill from "./user_pill";
import type {UserPillData} from "./user_pill";

function person_matcher(query: string, item: User): boolean {
    return (
        people.is_known_user_id(item.user_id) && typeahead_helper.query_matches_person(query, item)
    );
}

function group_matcher(query: string, item: UserGroup): boolean {
    return typeahead_helper.query_matches_name(query, item);
}

type TypeaheadItem = UserGroupPillData | StreamPillData | UserPillData;

export function set_up(
    $input: JQuery,
    pills: CombinedPillContainer,
    opts: {
        user: boolean;
        user_group?: boolean;
        stream?: boolean;
        user_source?: () => User[];
        exclude_bots?: boolean;
        update_func?: () => void;
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
        items: 5,
        fixed: true,
        dropup: true,
        source(query: string): TypeaheadItem[] {
            let source: TypeaheadItem[] = [];
            if (include_streams(query)) {
                // If query starts with # we expect,
                // only stream suggestions so we simply
                // return stream source.
                return stream_pill.typeahead_source(pills);
            }

            if (include_user_groups) {
                source = [...source, ...user_group_pill.typeahead_source(pills)];
            }

            if (include_users) {
                if (opts.user_source !== undefined) {
                    // If user_source is specified in opts, it
                    // is given priority. Otherwise we use
                    // default user_pill.typeahead_source.
                    const users: UserPillData[] = opts.user_source().map((user) => ({
                        ...user,
                        type: "user",
                    }));
                    source = [...source, ...users];
                } else {
                    source = [...source, ...user_pill.typeahead_source(pills, exclude_bots)];
                }
            }
            return source;
        },
        highlighter_html(item: TypeaheadItem, query: string): string {
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
            return typeahead_helper.render_person({
                ...item,
                is_broadcast: undefined,
            });
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
                    if (match.type === "user" && people.is_known_user_id(match.user_id)) {
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

            return typeahead_helper.sort_recipients({
                users,
                query,
                current_stream_id: undefined,
                current_topic: undefined,
                groups,
                max_num_items: undefined,
            });
        },
        updater(item: TypeaheadItem, query: string): undefined {
            if (include_streams(query) && item.type === "stream") {
                stream_pill.append_stream(item, pills);
            } else if (include_user_groups && item.type === "user_group") {
                user_group_pill.append_user_group(item, pills);
            } else if (
                include_users &&
                item.type === "user" &&
                people.is_known_user_id(item.user_id)
            ) {
                user_pill.append_user(item, pills);
            }

            $input.trigger("focus");
            if (opts.update_func) {
                opts.update_func();
            }
        },
        stopAdvance: true,
    });
}
