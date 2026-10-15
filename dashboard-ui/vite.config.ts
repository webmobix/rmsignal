import tailwindcss from "@tailwindcss/vite";
import { devtools } from "@tanstack/devtools-vite";

import { tanstackStart } from "@tanstack/react-start/plugin/vite";

import viteReact from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import { defineConfig } from "vite";

const apiTarget = process.env.RM_API_URL ?? "http://127.0.0.1:8765";

const config = defineConfig({
	resolve: { tsconfigPaths: true },
	plugins: [
		devtools(),
		nitro({
			rollupConfig: { external: [/^@sentry\//] },
			routeRules: { "/api/**": { proxy: `${apiTarget}/api/**` } },
		}),
		tailwindcss(),
		tanstackStart(),
		viteReact(),
	],
});

export default config;
