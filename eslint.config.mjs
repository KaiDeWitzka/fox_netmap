import js from "@eslint/js";
import globals from "globals";

// Geteilte Globals: mehrere klassische Script-Tags teilen sich den globalen Scope
// (index.html laedt i18n.js, icons.js, vendor/cytoscape.min.js, app.js in dieser Reihenfolge).
const sharedGlobals = {
  ApiError: "readonly",
  api: "readonly",
  apiJson: "readonly",
  I18N: "readonly",
  LANGS: "readonly",
  iconUri: "readonly",
  iconKeyFor: "readonly",
  CATEGORY_ICON_KEYS: "readonly",
  cytoscape: "readonly",
};

export default [
  {
    ignores: ["app/static/vendor/**"], // D-5: minifiziertes Fremdfile (cytoscape) nicht linten
  },
  {
    files: ["app/static/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      sourceType: "script",
      globals: { ...globals.browser, ...sharedGlobals },
    },
    rules: {
      "no-unused-vars": ["warn", { caughtErrors: "none" }],
    },
  },
  {
    files: ["tests/**/*.mjs", "eslint.config.mjs"],
    ...js.configs.recommended,
    languageOptions: {
      sourceType: "module",
      globals: { ...globals.node },
    },
    rules: {
      "no-unused-vars": ["warn", { caughtErrors: "none" }],
    },
  },
];
