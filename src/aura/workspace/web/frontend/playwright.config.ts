import {defineConfig} from "@playwright/test";

const webServer:any[]=[{
  command:"vite preview --host 127.0.0.1 --port 4183",
  url:"http://127.0.0.1:4183/assets/representation/",
  reuseExistingServer:true,
}];

if(process.env.AURA_E2E_MOCK_ONLY!=="1")webServer.push({
  command:"python -c \"from aura.workspace.server import create_app; import uvicorn; uvicorn.run(create_app(storage_mode='memory'),host='127.0.0.1',port=4184)\"",
  url:"http://127.0.0.1:4184/health/ready",
  reuseExistingServer:true,
});

export default defineConfig({
  testDir:"e2e",
  timeout:45_000,
  use:{baseURL:"http://127.0.0.1:4183/assets/representation/",channel:"msedge",headless:true},
  webServer,
});
