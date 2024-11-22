/**
 * Convert a value to an array, in a way compatible with the Handlebars `each`
 * helper.
 */
export function to_array<T>(values: T[] | Iterable<T> | Record<string, T> | undefined): T[] {
    if (typeof values !== "object") {
        return [];
    } else if (Array.isArray(values)) {
        return values;
    } else if (Symbol.iterator in values) {
        return [...values];
    }
    return Object.values(values);
}

/**
 * Convert a value to boolean, in a way compatible with the Handlebars `if`
 * helper.
 */
export function to_bool(value: unknown): boolean {
    return value ? !Array.isArray(value) || value.length !== 0 : value === 0;
}
