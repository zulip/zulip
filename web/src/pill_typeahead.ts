import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import * as people from "./people";
import type {User} from "./people";
import * as stream_pill from "./stream_pill";
import type {StreamSubscription} from "./sub_store";
import * as typeahead_helper from "./typeahead_helper";
import type {UserOrMention} from "./typeahead_helper";
import * as user_group_pill from "./user_group_pill";
import * as user_groups from "./user_groups";
import type {UserGroup} from "./user_groups";
import * as user_pill from "./user_pill";

function person_matcher(query: string, item: User): boolean {
    if (people.is_known_user(item)) {
        return typeahead_helper.query_matches_person(query, item);
    }
    return false;
}

function group_matcher(query: string, item: UserGroup): boolean {
    if (user_groups.is_user_group(item)) {
        return typeahead_helper.query_matches_name(query, item);
    }
    return false;
}

type StreamRecipient = StreamSubscription & {type: "stream"};
export type UserGroupRecipient = UserGroup & {type: "user_group"};
export type UserRecipient = UserOrMention & {type: "user"};

export type TypeaheadItem = StreamRecipient | UserGroupRecipient | UserRecipient;

export function set_up(
    $input: JQuery<HTMLInputElement>,
    pills: any,
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

    $input.typeahead({
        items: 5,
        fixed: true,
        dropup: true,
        source(): TypeaheadItem[] {
            let source: TypeaheadItem[] = [];
            if (include_streams(this.query)) {
                // If query starts with # we expect,
                // only stream suggestions so we simply
                // return stream source.
                return stream_pill.typeahead_source(pills).map((stream: StreamSubscription) => ({
                    ...stream,
                    type: "stream",
                }));
            }

            if (include_user_groups) {
                const user_group_pills: UserGroupRecipient[] = user_group_pill
                    .typeahead_source(pills)
                    .map((user_group: UserGroup) => ({
                        ...user_group,
                        type: "user_group",
                    }));
                source = [...source, ...user_group_pills];
            }

            if (include_users) {
                let user_pills: UserRecipient[];
                if (opts.user_source !== undefined) {
                    // If user_source is specified in opts, it
                    // is given priority. Otherwise we use
                    // default user_pill.typeahead_source.
                    user_pills = opts.user_source().map((user: User) => ({
                        ...user,
                        is_broadcast: undefined,
                        type: "user",
                    }));
                } else {
                    user_pills = user_pill
                        .typeahead_source(pills, exclude_bots)
                        .map((user: User) => ({
                            ...user,
                            is_broadcast: undefined,
                            type: "user",
                        }));
                }
                source = [...source, ...user_pills];
            }
            return source;
        },
        highlighter(item: TypeaheadItem): string {
            if (include_streams(this.query)) {
                assert(item.type === "stream");
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
        matcher(item: TypeaheadItem): boolean {
            let query = this.query.toLowerCase();
            query = query.replaceAll("\u00A0", " ");

            if (include_streams(query)) {
                assert(item.type === "stream");
                query = query.trim().slice(1);
                return item.name.toLowerCase().includes(query);
            }

            let matches = false;
            if (include_user_groups && item.type === "user_group") {
                matches = matches || group_matcher(query, item);
            }

            if (include_users && item.type === "user") {
                assert(item.is_broadcast === undefined);
                matches = matches || person_matcher(query, item);
            }
            return matches;
        },
        sorter(matches: TypeaheadItem[]): TypeaheadItem[] {
            const query = this.query;
            if (include_streams(query)) {
                const asserted_streams = matches.map((match) => {
                    assert(match.type === "stream");
                    return match;
                });
                const sorted_streams = typeahead_helper.sort_streams(
                    asserted_streams,
                    query.trim().slice(1),
                );
                return sorted_streams.map((stream) => ({
                    ...stream,
                    type: "stream",
                }));
            }

            let users: UserRecipient[] = [];
            if (include_users) {
                users = matches
                    .filter(
                        (match) =>
                            match.type === "user" &&
                            match.is_broadcast === undefined &&
                            people.is_known_user(match),
                    )
                    .map((match) => {
                        assert(match.type === "user");
                        assert(match.is_broadcast === undefined);
                        return match;
                    });
            }

            let groups: UserGroupRecipient[] = [];
            if (include_user_groups) {
                groups = matches
                    .filter(
                        (match) => match.type === "user_group" && user_groups.is_user_group(match),
                    )
                    .map((match) => {
                        assert(match.type === "user_group");
                        return match;
                    });
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
        updater(item: TypeaheadItem): void {
            if (include_streams(this.query)) {
                assert(item.type === "stream");
                stream_pill.append_stream(item, pills);
            } else if (include_user_groups && item.type === "user_group") {
                user_group_pill.append_user_group(item, pills);
            } else if (
                include_users &&
                item.type === "user" &&
                item.is_broadcast === undefined &&
                people.is_known_user(item)
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
