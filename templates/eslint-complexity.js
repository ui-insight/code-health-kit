// Merge into eslint.config.js (flat config).
//
// Complexity ratchet: new code stays at MAX_COMPLEXITY or below. Each file
// listed in COMPLEXITY_CAPS is capped at its current worst score, so it can't
// get worse. scripts/bootstrap_caps.py prints this object for an existing
// project. Lower a cap as the file is refactored, and delete the entry once it
// reaches the default.
const MAX_COMPLEXITY = 20
const COMPLEXITY_CAPS = {
  // 'src/pages/ExamplePage.tsx': 34,
}

export default defineConfig([
  // ...your existing config objects, with this rule added to the main one:
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      complexity: ['error', MAX_COMPLEXITY],
    },
  },
  // Per-file caps come last so they override the default.
  ...Object.entries(COMPLEXITY_CAPS).map(([file, cap]) => ({
    files: [file],
    rules: { complexity: ['error', cap] },
  })),
])
