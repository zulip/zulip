// We need to use an older version of url-template because our test suite setup does not
// support testing with ESM-only modules. Unfortunately, the older version also happens to
// not have type definitions, so we maintain our own copy of it. This is adapted from:
// https://github.com/bramstein/url-template/blob/a8e204a92de3168a56ef2e528ae4d841287636fd/lib/url-template.d.ts

declare module "url-template" {
    export type PrimitiveValue = string | number | boolean | null;

    export type Template = {
        expand(
            context: Record<
                string,
                PrimitiveValue | PrimitiveValue[] | Record<string, PrimitiveValue>
            >,
        ): string;
    };

    export function parse(template: string): Template;
}
