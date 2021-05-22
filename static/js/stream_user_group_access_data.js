import _ from "lodash";
// This stores stream_user_group_access objects mapped according to their id.
let access_objs_by_id_map;

// This stores all the stream_user_group_access objects of a stream as a array
// with key as stream_id.
let access_objs_by_stream_map;
export function init() {
    access_objs_by_id_map = new Map();
    access_objs_by_stream_map = new Map();
}
// init function helps to clear data in tests.
init();

const stream_user_group_access_fields = ["id", "stream_id", "group_id"];

export function add_access_obj(access_obj) {
    const cleaned_obj = _.pick(access_obj, stream_user_group_access_fields);
    access_objs_by_id_map.set(cleaned_obj.id, cleaned_obj);
    add_to_stream_map(access_obj);
}

export function add_to_stream_map(access_obj) {
    // This should be called from add_access_obj only so that data in both maps is
    // always in sync.

    // Adds new stream user_group_access obj in array of a stream only if it is
    // is already not present
    const cleaned_obj = _.pick(access_obj, stream_user_group_access_fields);
    if (access_objs_by_stream_map.has(cleaned_obj.stream_id)) {
        if (!can_user_group_post(cleaned_obj.group_id, cleaned_obj.stream_id)) {
            let allowed_access_objs = access_objs_by_stream_map.get(access_obj.stream_id);
            allowed_access_objs = [...allowed_access_objs, cleaned_obj];
            access_objs_by_stream_map.set(cleaned_obj.stream_id, allowed_access_objs);
        }
    } else {
        access_objs_by_stream_map.set(cleaned_obj.stream_id, [cleaned_obj]);
    }
}

export function delete_access_obj(obj_id) {
    let stream_id = null;
    if (access_objs_by_id_map.has(obj_id)) {
        stream_id = access_objs_by_id_map.get(obj_id).stream_id;
        access_objs_by_id_map.delete(obj_id);
    } else {
        // addition and removal from both the maps is performed simultaneously
        // so it is safe to ignore removal from stream map if obj is not
        // present in id map.
        return;
    }
    // remove from stream map
    let allowed_access_objs = access_objs_by_stream_map.get(stream_id);
    allowed_access_objs = allowed_access_objs.filter((item) => item.id !== obj_id);
    access_objs_by_stream_map.set(stream_id, allowed_access_objs);
}

export function can_user_group_post(group_id, stream_id) {
    const allowed_access_objs = access_objs_by_stream_map.get(stream_id);
    for (const obj of allowed_access_objs) {
        if (obj.group_id === group_id) {
            return true;
        }
    }
    return false;
}

export function get_stream_user_group_access_obj_by_id(id) {
    return access_objs_by_id_map.get(id);
}

export function get_allowed_user_groups_access_obj_for_stream(stream_id) {
    if (access_objs_by_stream_map.has(stream_id)) {
        return access_objs_by_stream_map.get(stream_id);
    }
    return [];
}

export function get_allowed_user_group_ids(stream_id) {
    let allowed_user_groups = get_allowed_user_groups_access_obj_for_stream(stream_id);
    allowed_user_groups = allowed_user_groups.map((item) => item.group_id);
    return allowed_user_groups;
}

export function initialize(params) {
    for (const obj of params.stream_user_group_access_data) {
        add_access_obj(obj);
    }
}
