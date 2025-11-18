import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Use empty string as prefix to load ALL env vars (not just VITE_ prefixed)
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      // Proxy API requests from browser to backend
      // This allows the browser to make requests to http://localhost:5173/api/...
      // which Vite proxies to the backend service in Docker network
      proxy: {
        '/api': {
          // Use API_BACKEND_URL (without VITE_ prefix) so it's NOT exposed to browser
          target: env.API_BACKEND_URL || process.env.API_BACKEND_URL || 'http://backend:8000',
          changeOrigin: true,
          secure: false,
          ws: true, // Enable WebSocket proxying
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request to the Target:', req.method, req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        },
      },
    },
  }
})
