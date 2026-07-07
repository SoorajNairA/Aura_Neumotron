import { defineConfig } from "@playwright/test"
export default defineConfig({testDir:"e2e",timeout:45_000,use:{baseURL:"http://127.0.0.1:4183/assets/representation/",channel:"msedge",headless:true},webServer:{command:"vite preview --host 127.0.0.1 --port 4183",url:"http://127.0.0.1:4183/assets/representation/",reuseExistingServer:true}})
