import {Filter} from "./filter";
import * as hash_util from "./hash_util";

export class MessageListDataCache {
    constructor() {
        this._objects = new Map();
    }

    _get_key(filter) {
        // The MLDCache API uses the filter object as the key.
        // Internally, we serialize it, so this function
        // should be called when only we want to access or
        // create a stored MLD object.
        return hash_util.operators_to_hash(filter.operators());
    }

    get(filter) {
        const key = this._get_key(filter);
        return this._objects.get(key);
    }

    add(mld) {
        if (!mld.filter.can_apply_locally() || mld.empty()) {
            return;
        }
        const key = this._get_key(mld.filter);
        this._objects.set(key, mld);
    }

    _get_by_key(key) {
        return this._objects.get(key);
    }

    _get_key_from_operators(raw_operators) {
        const filter = new Filter(raw_operators);
        const operators = filter.operators();
        return hash_util.operators_to_hash(operators);
    }

    get_valid_mlds(filter) {
        const operators = filter.operators();
        const key = hash_util.operators_to_hash(operators);
        const keys = [key];

        if (filter.contains_only_private_messages()) {
            if (keys[0].includes("pm-with") || keys[0].includes("group-pm-with")) {
                const is_private_operator = [{operator: "is", operand: "private"}];
                keys.push(this._get_key_from_operators(is_private_operator));
            }
        } else {
            if (keys[0].includes("topic")) {
                const stream_operator = [filter.operators()[0]];
                keys.push(this._get_key_from_operators(stream_operator));
            }
        }

        const mld_objects = keys.map((key) => this._get_by_key(key));
        return mld_objects.filter((mld) => mld !== undefined);
    }

    has(filter) {
        const key = this._get_key(filter);
        return this._objects.has(key);
    }

    delete(filter) {
        const key = this._get_key(filter);
        this._objects.delete(key);
    }

    keys() {
        return Array.from(this._objects.keys());
    }

    entries() {
        return this.keys().map((key) => this._get_by_key(key));
    }

    empty() {
        this._objects = new Map();
    }
}

export const mld_cache = new MessageListDataCache();
