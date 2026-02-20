import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
    include: ["src/test/**/*.{test,spec}.{js,jsx,ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: [
        "src/pages/Home.jsx",
        "src/pages/Posts.jsx",
        "src/pages/Account.jsx"
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 60,
        statements: 80
      }
    }
  }
})
