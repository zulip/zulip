/*

This module has shims to help us break circular dependencies.
We eventually want to to move the actual implementations into
new modules.  When we do this, you may need to fix node tests
that still refer to the old name.
*/

var narrow_state = {}; // global, should be made into module
narrow_state.set_compose_defaults = narrow.set_compose_defaults;

