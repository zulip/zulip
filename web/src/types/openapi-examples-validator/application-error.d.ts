export enum ErrorType {
    jsENOENT = "ENOENT",
    jsonPathNotFound = "JsonPathNotFound",
    errorAndErrorsMutuallyExclusive = "ErrorErrorsMutuallyExclusive",
    parseError = "ParseError",
    validation = "Validation",
}

export type ApplicationErrorOptions = {
    instancePath?: string;
    examplePath?: string;
    exampleFilePath?: string;
    keyword?: string;
    message?: string;
    mapFilePath?: string;
    params?: {
        path?: string;
        missingProperty?: string;
        type?: string;
    };
    schemaPath?: string;
};

/**
 * Unified application-error
 */
export class ApplicationError {
    /**
     * Factory-function, which is able to consume validation-errors and
     * JS-errors. If a validation error is passed, all properties will be
     * adopted.
     *
     * @param err - Javascript-, validation- or custom-error, to create the
     * application-error from
     * @returns Unified application-error instance
     */
    static create(err: Error): ApplicationError;

    /**
     * Constructor
     *
     * @param type - Type of error (see statics)
     * @param options - Optional properties
     */
    constructor(type: ErrorType, options?: ApplicationErrorOptions);

    type: ErrorType;
    instancePath?: string;
    examplePath?: string;
    exampleFilePath?: string;
    keyword?: string;
    message?: string;
    mapFilePath?: string;
    params?: {
        path?: string;
        missingProperty?: string;
        type?: string;
    };
    schemaPath?: string;
}
