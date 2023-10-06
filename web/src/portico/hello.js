// Mark this as a module for ESLint and Webpack.
export {};

function get_new_rand(oldRand, max) {
    const newRand = Math.floor(Math.random() * max);
    return newRand === oldRand ? get_new_rand(newRand, max) : newRand;
}

function get_random_item_from_array(array) {
    return array[Math.floor(Math.random() * array.length)];
}

const current_clint_logo_class_names = new Set([
    "client-logos__logo_akamai",
    "client-logos__logo_tum",
    "client-logos__logo_wikimedia",
    "client-logos__logo_rust",
    "client-logos__logo_dr_on_demand",
    "client-logos__logo_maria",
]);
const future_logo_class_names = new Set([
    "client-logos__logo_pilot",
    "client-logos__logo_recurse",
    "client-logos__logo_level_up",

    "client-logos__logo_layershift",
    "client-logos__logo_julia",
    "client-logos__logo_ucsd",
    "client-logos__logo_lean",
    "client-logos__logo_asciidoc",
]);
let current_clint_logo_class_namesIndex = 0;
function update_client_logo() {
    if (document.hidden) {
        return;
    }
    const logos = [...document.querySelectorAll("[class^='client-logos__']")];
    current_clint_logo_class_namesIndex = get_new_rand(
        current_clint_logo_class_namesIndex,
        logos.length,
    );
    const el = logos[current_clint_logo_class_namesIndex];

    const oldClass = el.className;
    el.className = "";
    current_clint_logo_class_names.delete(oldClass);
    const newClass = get_random_item_from_array([...future_logo_class_names.values()]);
    future_logo_class_names.delete(newClass);
    el.className = newClass;
    current_clint_logo_class_names.add(newClass);
    future_logo_class_names.add(oldClass);
}

setInterval(update_client_logo, 2500);
