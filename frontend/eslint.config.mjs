import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This app's pages are plain client components that fetch their own
      // data in a useEffect on mount/param-change (no Suspense boundaries,
      // no data-fetching library) - the idiomatic pre-Suspense React
      // pattern, used consistently across every page. This rule flags that
      // pattern everywhere it appears; disabling it project-wide documents
      // the one real decision instead of repeating the same justification
      // at every call site.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
