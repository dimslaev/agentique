import fs from "node:fs"
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"

// Serve the prerendered blog in dev. `prerender-blog.ts` only runs after
// `vite build`, so without this /blog/ falls through to the SPA's 404.
// shortcut: styles come from the last build, not live — `bun run build`
// after changing blog markup or styles.
function devBlog(): import("vite").Plugin {
  const dist = path.resolve(__dirname, "dist")
  const serve = (res, file: string, type: string) => {
    res.setHeader("Content-Type", type)
    fs.createReadStream(file).pipe(res)
  }
  return {
    name: "dev-blog",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0]
        if (url.startsWith("/assets/")) {
          const file = path.join(dist, url)
          return fs.existsSync(file) ? serve(res, file, "text/css") : next()
        }
        if (!url.startsWith("/blog/") && url !== "/sitemap.xml") return next()
        const rel =
          url === "/blog" || url === "/blog/"
            ? "blog/index.html"
            : `blog${url.replace(/^\/blog/, "").replace(/\/$/, "")}/index.html`
        const file = path.join(dist, rel)
        return fs.existsSync(file) ? serve(res, file, "text/html") : next()
      })
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
      generatedRouteTree: "./src/route-tree.gen.ts",
    }),
    react(),
    tailwindcss(),
    devBlog(),
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      // Not a frontend route — proxied so an MCP client points at the same
      // path in dev (localhost:5173/mcp) as in prod (agentique.ch/mcp).
      "/mcp": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
