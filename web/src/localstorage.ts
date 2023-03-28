import * as blueslip from "./blueslip";

type FormData<T = unknown> = {
    __valid: boolean;
    data: T;
    expires: number | null;
};

const ls = {
    // check if the datestamp is from before now and if so return true.
    isExpired(stamp: string | number | Date): boolean {
        return new Date(stamp) < new Date();
    },

    // return the localStorage key that is bound to a version of a key.
    formGetter(version: number, name: string): string {
        return `ls__${version}__${name}`;
    },

    // create a formData object to put in the data, a signature that it was
    // created with this library, and when it expires (if ever).
    formData<T = unknown>(data: T, expires: number): FormData<T> {
        return {
            __valid: true,
            data,
            expires: Date.now() + expires,
        };
    },

    getData<T = unknown>(version: number, name: string): FormData<T> | undefined {
        const key = this.formGetter(version, name);
        let data: FormData<T> | null = null;

        try {
            const raw_data = localStorage.getItem(key);

            if (typeof raw_data === "string") {
                data = JSON.parse(raw_data);
            }
        } catch {
            // data stays undefined
        }

        if (
            data &&
            data.__valid &&
            // JSON forms of data with `Infinity` turns into `null`,
            // so if null then it hasn't expired since nothing was specified.
            (data.expires === null || !ls.isExpired(data.expires))
        ) {
            return data;
        }

        return undefined;
    },

    // set the wrapped version of the data into localStorage.
    setData(version: number, name: string, data: any, expires: number): void {
        const key = this.formGetter(version, name);
        const val = this.formData(data, expires);

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
        condition_checker: (value: any) => boolean,
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
            let value: string | null = null;
            let value_set = false;

            try {
                value = localStorage.getItem(key);
                value_set = true;
            } catch {
                // Do nothing if the fetch fails
            }

            if (value_set && condition_checker(value)) {
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
        callback: (old_data: any) => T,
    ): T | undefined {
        const old_form_data = this.getData(v1, name);
        this.removeData(v1, name);

        if (old_form_data && old_form_data.__valid) {
            const data = callback(old_form_data.data);
            this.setData(v2, name, data, Number.POSITIVE_INFINITY);

            return data;
        }

        return undefined;
    },
};

// return a new function instance that has instance-scoped variables.
export const localstorage = function () {
    const _data = {
        VERSION: 1,
        expires: Number.POSITIVE_INFINITY,
        expiresIsGlobal: false,
    };

    const prototype = {
        // `expires` should be a Number that represents the number of ms from
        // now that this should expire in.
        // this allows for it to either be set only once or permanently.
        setExpiry(expires: number, isGlobal: boolean) {
            _data.expires = expires;
            _data.expiresIsGlobal = isGlobal || false;

            return this;
        },

        // Here unknown type denotes
        get<T = unknown>(name: string): T | undefined {
            const form_data = ls.getData<T>(_data.VERSION, name);

            if (form_data) {
                return form_data.data;
            }

            return undefined;
        },

        set(name: string, data: any): boolean {
            if (_data.VERSION !== undefined) {
                ls.setData(_data.VERSION, name, data, _data.expires);

                // if the expires attribute was not set as a global, then
                // make sure to return it back to Infinity to not impose
                // constraints on the next key.
                if (!_data.expiresIsGlobal) {
                    _data.expires = Number.POSITIVE_INFINITY;
                }

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
            condition_checker: (value: any) => boolean,
        ): void {
            ls.removeDataRegexWithCondition(_data.VERSION, name, condition_checker);
        },

        migrate<T = unknown>(
            name: string,
            v1: number,
            v2: number,
            callback: (old_data: any) => T,
        ): T | undefined {
            return ls.migrate<T>(name, v1, v2, callback);
        },
    };

    // set a new master version for the LocalStorage instance.
    Object.defineProperty(prototype, "version", {
        get(): number {
            return _data.VERSION;
        },
        set(version: number): void {
            _data.VERSION = version;
        },
    });

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
