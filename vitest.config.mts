import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      include: [
        "src/app/components/**/*.tsx",
        "src/lib/backend.ts",
        "src/lib/generation-request.ts",
      ],
      exclude: ["**/*.test.*"],
      thresholds: { lines: 70 },
      reporter: ["text", "html"],
    },
  },
});
