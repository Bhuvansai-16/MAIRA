import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  
  // Build optimizations
  build: {
    // Enable source maps for production debugging (optional)
    sourcemap: false,
    
    // Minification
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console.logs in production
        drop_debugger: true,
      },
    },
    
    // Chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-ui': ['framer-motion', 'lucide-react', 'sonner'],
          'vendor-markdown': ['react-markdown', 'remark-gfm'],
          'vendor-supabase': ['@supabase/supabase-js'],
        },
      },
    },
    
    // Chunk size warnings
    chunkSizeWarningLimit: 1000,
  },
  
  // Development server
  server: {
    port: 5173,
    strictPort: false,
    host: true, // Allow external access
  },
  
  // Preview server (for testing production builds)
  preview: {
    port: 4173,
    strictPort: false,
  },
  
  // Resolve aliases
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  
  // Environment variable prefix
  envPrefix: 'VITE_',
})
