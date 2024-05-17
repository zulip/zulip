import generated_pygments_data from "../generated/pygments_data.json";

type PygmentsLanguage = {priority: number; pretty_name: string};
const langs: Record<string, PygmentsLanguage | undefined> = generated_pygments_data.langs;

export {langs};
