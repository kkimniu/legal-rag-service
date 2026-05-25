import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite config stays small so Docker and CI can override behavior with env vars.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
