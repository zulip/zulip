import type {AcceptedPlugin, PluginCreator} from "postcss";

export type PostCSSImportOptions = {
    filter?: (path: string) => boolean;
    root?: string;
    path?: string | string[];
    plugins?: AcceptedPlugin[];
    resolve?: (
        id: string,
        basedir: string,
        importOptions: PostCSSImportOptions,
        astNode: unknown,
    ) => string | string[] | Promise<string | string[]>;
    load?: (filename: string, importOptions: PostCSSImportOptions) => string | Promise<string>;
    skipDuplicates?: boolean;
    addModulesDirectories?: string[];
    warnOnEmpty?: boolean;
};

declare const postcssImport: PluginCreator<PostCSSImportOptions>;
export default postcssImport;
