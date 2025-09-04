import type {ApplicationError} from "./application-error.d.ts";

declare namespace OpenApiExamplesValidator {
    export type ValidationStatistics = {
        schemasWithExamples: number;
        examplesTotal: number;
        examplesWithoutSchema: number;
        matchingFilePathsMapping?: number | undefined;
    };

    export type ValidationResponse = {
        valid: boolean;
        statistics: ValidationStatistics;
        errors: ApplicationError[];
    };

    /**
     * Validates OpenAPI-spec with embedded examples.
     *
     * @param openapiSpec - OpenAPI-spec
     */
    export function validateExamples(
        openapiSpec: object,
        options?: {
            /**
             * Don't allow properties that are not defined in the schema
             */
            noAdditionalProperties?: boolean | undefined;
            /**
             * Make all properties required
             */
            allPropertiesRequired?: boolean | undefined;
            /**
             * List of datatype formats that shall be ignored (to prevent
             * "unsupported format" errors). If an Array with only one string is
             * provided where the formats are separated with `\n`, the entries will
             * be expanded to a new array containing all entries.
             */
            ignoreFormats?: string[] | undefined;
        },
    ): Promise<ValidationResponse>;
    // eslint-disable-next-line unicorn/no-named-default
    export {validateExamples as default};

    /**
     * Validates OpenAPI-spec with embedded examples.
     *
     * @param filePath - File-path to the OpenAPI-spec
     */
    export function validateFile(
        filePath: string,
        options?: {
            /**
             * Don't allow properties that are not defined in the schema
             */
            noAdditionalProperties?: boolean | undefined;
            /**
             * Make all properties required
             */
            allPropertiesRequired?: boolean | undefined;
            /**
             * List of datatype formats that shall be ignored (to prevent
             * "unsupported format" errors). If an Array with only one string is
             * provided where the formats are separated with `\n`, the entries will
             * be expanded to a new array containing all entries.
             */
            ignoreFormats?: string[] | undefined;
        },
    ): Promise<ValidationResponse>;

    /**
     * Validates examples by mapping-files.
     *
     * @param filePathSchema - File-path to the OpenAPI-spec
     * @param globMapExternalExamples - File-path (globs are supported) to the
     * mapping-file containing JSON-paths to schemas as key and a single file-path
     * or Array of file-paths to external examples
     */
    export function validateExamplesByMap(
        filePathSchema: string,
        globMapExternalExamples: string,
        options?: {
            /**
             * Change working directory for resolving the example-paths (relative to
             * the mapping-file)
             */
            cwdToMappingFile?: boolean | undefined;
            /**
             * Don't allow properties that are not defined in the schema
             */
            noAdditionalProperties?: boolean | undefined;
            /**
             * Make all properties required
             */
            allPropertiesRequired?: boolean | undefined;
            /**
             * List of datatype formats that shall be ignored (to prevent
             * "unsupported format" errors). If an Array with only one string is
             * provided where the formats are separated with `\n`, the entries will
             * be expanded to a new array containing all entries.
             */
            ignoreFormats?: string[] | undefined;
        },
    ): Promise<ValidationResponse>;

    /**
     * Validates a single external example.
     *
     * @param filePathSchema - File-path to the OpenAPI-spec
     * @param pathSchema - JSON-path to the schema
     * @param filePathExample - File-path to the external example-file
     */
    export function validateExample(
        filePathSchema: string,
        pathSchema: string,
        filePathExample: string,
        options?: {
            /**
             * Don't allow properties that are not described in the schema
             */
            noAdditionalProperties?: boolean | undefined;
            /**
             * Make all properties required
             */
            allPropertiesRequired?: boolean | undefined;
            /**
             * List of datatype formats that shall be ignored (to prevent
             * "unsupported format" errors). If an Array with only one string is
             * provided where the formats are separated with `\n`, the entries will
             * be expanded to a new array containing all entries.
             */
            ignoreFormats?: string[] | undefined;
        },
    ): Promise<ValidationResponse>;
}

export default OpenApiExamplesValidator;
