import generated_pygments_data from "../generated/pygments_data.json";

type PygmentsLanguage = {priority: number; pretty_name: string};
export let langs: Record<string, PygmentsLanguage | undefined> = generated_pygments_data.langs;

export function rewire_langs(value: typeof langs): void {
    langs = value;
}
