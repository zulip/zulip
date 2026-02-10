import type {Linter, Rule} from "eslint";

declare const eslintPluginNoJquery: {
    rules: Record<string, Rule.RuleModule>;
    configs: {
        recommended: Linter.LegacyConfig;
        slim: Linter.LegacyConfig;
        deprecated: Linter.LegacyConfig;
        ["deprecated-3.7"]: Linter.LegacyConfig;
        ["deprecated-3.6"]: Linter.LegacyConfig;
        ["deprecated-3.5"]: Linter.LegacyConfig;
        ["deprecated-3.4"]: Linter.LegacyConfig;
        ["deprecated-3.3"]: Linter.LegacyConfig;
        ["deprecated-3.2"]: Linter.LegacyConfig;
        ["deprecated-3.1"]: Linter.LegacyConfig;
        ["deprecated-3.0"]: Linter.LegacyConfig;
        ["deprecated-2.2"]: Linter.LegacyConfig;
        ["deprecated-2.1"]: Linter.LegacyConfig;
        ["deprecated-2.0"]: Linter.LegacyConfig;
        ["deprecated-1.12"]: Linter.LegacyConfig;
        ["deprecated-1.11"]: Linter.LegacyConfig;
        ["deprecated-1.10"]: Linter.LegacyConfig;
        ["deprecated-1.9"]: Linter.LegacyConfig;
        ["deprecated-1.8"]: Linter.LegacyConfig;
        ["deprecated-1.7"]: Linter.LegacyConfig;
        ["deprecated-1.6"]: Linter.LegacyConfig;
        ["deprecated-1.5"]: Linter.LegacyConfig;
        ["deprecated-1.4"]: Linter.LegacyConfig;
        ["deprecated-1.3"]: Linter.LegacyConfig;
        ["deprecated-1.2"]: Linter.LegacyConfig;
        ["deprecated-1.1"]: Linter.LegacyConfig;
        ["deprecated-1.0"]: Linter.LegacyConfig;
        all: Linter.LegacyConfig;
    };
};

export = eslintPluginNoJquery;
