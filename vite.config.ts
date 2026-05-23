import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

function resolveAllowedHosts() {
  const raw = (process.env.VITE_ALLOWED_HOSTS || '').trim()
  if (!raw) return undefined
  // Vite expects `true` to allow all hosts (useful for tunnels).
  if (raw === 'all') return true as const
  return raw.split(',').map((s) => s.trim()).filter(Boolean)
}

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    allowedHosts: resolveAllowedHosts(),
    proxy: {
      // 后端桥接 API
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
