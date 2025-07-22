import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";

const formDataSchema = z.object({
    data: z.unknown(),
    __valid: z.literal(true),
});

type FormData = z.infer<typeof formDataSchema>;

export type LocalStorage = {
    get: (name: string) => unknown;
    set: (name: string, data: unknown) => boolean;
    remove: (name: string) => void;
    removeDataRegexWithCondition: (
        name: string,
        condition_checker: (value: unknown) => boolean,
    ) => void;
    migrate: <T = unknown>(
        name: string,
        v1: number,
        v2: number,
        callback: (data: unknown) => T,
    ) => T | undefined;
};

const ls = {
    // return the localStorage key that is bound to a version of a key.
    formGetter(version: number, name: string): string {
        return `ls__${version}__${name}`;
    },

    // create a formData object to put in the data and a signature that it was
    // created with this library.
    formData(data: unknown): FormData {
        return {
            data,
            __valid: true,
        };
    },

    getData(version: number, name: string): FormData | undefined {
        const key = this.formGetter(version, name);
        try {
            const raw_data = localStorage.getItem(key);
            if (raw_data === null) {
                return undefined;
            }
            return formDataSchema.parse(JSON.parse(raw_data));
        } catch {
            return undefined;
        }
    },

    // set the wrapped version of the data into localStorage.
    setData(version: number, name: string, data: unknown): void {
        const key = this.formGetter(version, name);
        const val = this.formData(data);

        localStorage.setItem(key, JSON.stringify(val));
    },

    // remove the key from localStorage and from memory.
    removeData(version: number, name: string): void {
        const key = this.formGetter(version, name);

        localStorage.removeItem(key);
    },

    // Remove keys which (1) map to a value that satisfies a
    // property tested by `condition_checker` and (2) which match
    // the pattern given by `name`.
    removeDataRegexWithCondition(
        version: number,
        regex: string,
        condition_checker: (value: unknown) => boolean,
    ): void {
        const key_regex = new RegExp(this.formGetter(version, regex));
        let keys: string[] = [];
        try {
            keys = Object.keys(localStorage);
        } catch {
            // Do nothing if we fail to fetch the local storage
        }

        keys = keys.filter((key) => key_regex.test(key));

        for (const key of keys) {
            let raw_data;
            try {
                raw_data = localStorage.getItem(key);
            } catch {
                continue;
            }
            if (raw_data === null) {
                continue;
            }
            const data = formDataSchema.parse(JSON.parse(raw_data));
            if (condition_checker(data.data)) {
                try {
                    localStorage.removeItem(key);
                } catch {
                    // Do nothing if deletion fails
                }
            }
        }
    },

    // migrate from an older version of a data src to a newer one with a
    // specified callback function.
    migrate<T = unknown>(
        name: string,
        v1: number,
        v2: number,
        callback: (oldData: unknown) => T,
    ): T | undefined {
        const old = this.getData(v1, name);
        this.removeData(v1, name);

        if (old?.__valid) {
            const data = callback(old.data);
            this.setData(v2, name, data);

            return data;
        }

        return undefined;
    },
};

// return a new function instance that has instance-scoped variables.
export const localstorage = function (): LocalStorage {
    const _data = {
        VERSION: 1,
    };

    const prototype = {
        get(name: string): unknown {
            const data = ls.getData(_data.VERSION, name);

            if (data) {
                return data.data;
            }

            return undefined;
        },

        set(name: string, data: unknown): boolean {
            if (_data.VERSION !== undefined) {
                ls.setData(_data.VERSION, name, data);
                return true;
            }

            return false;
        },

        // remove a key with a given version.
        remove(name: string): void {
            ls.removeData(_data.VERSION, name);
        },

        // Remove keys which (1) map to a value that satisfies a
        // property tested by `condition_checker` AND (2) which
        // match the pattern given by `name`.
        removeDataRegexWithCondition(
            name: string,
            condition_checker: (value: unknown) => boolean,
        ): void {
            ls.removeDataRegexWithCondition(_data.VERSION, name, condition_checker);
        },

        migrate<T = unknown>(
            name: string,
            v1: number,
            v2: number,
            callback: (data: unknown) => T,
        ): T | undefined {
            return ls.migrate(name, v1, v2, callback);
        },

        // set a new master version for the LocalStorage instance.
        get version() {
            return _data.VERSION;
        },
        set version(version) {
            _data.VERSION = version;
        },
    };

    return prototype;
};

let warned_of_localstorage = false;

localstorage.supported = function supports_localstorage(): boolean {
    try {
        return window.localStorage !== undefined && window.localStorage !== null;
    } catch {
        if (!warned_of_localstorage) {
            blueslip.error(
                "Client browser does not support local storage, will lose socket message on reload",
            );
            warned_of_localstorage = true;
        }
        return false;
    }
};
