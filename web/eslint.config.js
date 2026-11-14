import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "src/shared/api/schema.d.ts", "public/mockServiceWorker.js"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Une fonctionnalité n'importe jamais le code interne d'une autre (taches-agents.md §8).
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/features", "@/features/**"],
              message:
                "Une fonctionnalité passe par le magasin partagé ou l'API, jamais par le code d'une autre.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/app/registry.ts", "vite.config.ts"],
    rules: { "no-restricted-imports": "off" },
  },
);
