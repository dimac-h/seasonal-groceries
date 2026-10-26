import { writeFileSync } from 'node:fs';
import { defineConfig } from 'vite';

// Builds straight into ../www, which HA serves from /seasonal_groceries_frontend/
// (see __init__.py's static path registration).
export default defineConfig({
  plugins: [
    {
      // emptyOutDir wipes www/.gitkeep, which keeps the (otherwise git-ignored)
      // directory in the repo so the integration still loads without a build.
      name: 'restore-www-gitkeep',
      closeBundle: () => writeFileSync('../www/.gitkeep', ''),
    },
  ],
  base: '/seasonal_groceries_frontend/',
  build: {
    outDir: '../www',
    emptyOutDir: true,
    lib: {
      entry: { 'seasonal-groceries-cards': 'src/main.ts' },
      formats: ['es'],
    },
    rollupOptions: {
      output: { entryFileNames: '[name].js' },
    },
  },
});
