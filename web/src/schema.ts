/*

These runtime schema validators are defensive and
should always succeed, so we don't necessarily want
to translate these.  These are very similar to server
side validators in zerver/lib/validator.py.

*/

export function check_string(var_name: string, val: string): string | undefined {
    if (typeof val !== "string") {
        return `${var_name} is not a string`;
    }

    return undefined;
}

/*
For `val` record, type of keys must be `string` and type of values
must be the same as type of second argument passed to validator functions
passed in as values in `fields` record.
*/
export function check_record<T>(
    var_name: string,
    val: Record<string, T>,
    fields: Record<string, (field_name: string, field_value: T) => string | undefined>,
): string | undefined {
    if (typeof val !== "object") {
        return `${var_name} is not a record`;
    }

    const field_results = Object.entries(fields).map(([field_name, f]) => {
        if (val[field_name] === undefined) {
            return `${field_name} is missing`;
        }

        return f(field_name, val[field_name]);
    });

    const msg = field_results.filter(Boolean).sort().join(", ");

    if (msg) {
        return `in ${var_name} ${msg}`;
    }

    return undefined;
}

/*
For `val` list, type of items must be the same as type of second
argument passed to `checker` function.
*/
export function check_array<T>(
    var_name: string,
    val: T[],
    checker: (item_name: string, item_value: T) => string | void,
): string | undefined {
    if (!Array.isArray(val)) {
        return `${var_name} is not an array`;
    }

    for (const item of val) {
        const msg = checker("item", item);

        if (msg) {
            return `in ${var_name} we found an item where ${msg}`;
        }
    }

    return undefined;
}
