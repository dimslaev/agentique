import fsd from "@feature-sliced/steiger-plugin"
import { defineConfig } from "steiger"

export default defineConfig([
  ...fsd.configs.recommended,
  {
    rules: {
      // Steiger counts references from FSD layers only, and routes/ is not
      // one, so every slice a route imports reads as unused.
      "fsd/insignificant-slice": "off",
    },
  },
])
