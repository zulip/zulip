import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	base: 'help-beta',
	integrations: [
		starlight({
			title: 'Zulip help center',
			pagination: false,
		}),
	],
});
