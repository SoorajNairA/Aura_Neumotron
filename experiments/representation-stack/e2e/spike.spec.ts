import { expect,test } from "@playwright/test"
test.beforeEach(async({page})=>{page.on("pageerror",error=>console.error("PAGE_ERROR",error));page.on("console",message=>console.log("BROWSER",message.type(),message.text()))})

test("loads separate curved CAD parts and interaction controls",async({page})=>{
  await page.goto("/");await expect(page.getByTestId("three-canvas")).toBeVisible();await expect(page.getByTestId("cad-status")).toContainText("succeeded",{timeout:35_000})
  await expect(page.locator("[data-cad-part]")).toHaveCount(3);await page.locator('[data-cad-part="component-reservoir"]').click();await expect(page.getByTestId("selected-id")).toHaveText("component-reservoir")
  console.log("CAD_METRICS",await page.locator("[data-cad-part]").allTextContents(),await page.locator(".metric").allTextContents())
  await page.locator('[data-symbol="M1"]').click();await expect(page.getByTestId("selected-id")).toHaveText("component-pump")
  await page.getByLabel("Explode").fill("1");await expect(page.getByLabel("Explode")).toHaveValue("1")
  await expect(page.getByTestId("schematic")).toBeVisible()
})
test("cross-highlights circuit and 3D semantic identities",async({page})=>{
  await page.goto("/");await page.locator('[data-symbol="Q1"]').click();await expect(page.getByTestId("selected-id")).toHaveText("component-driver");await expect(page.locator('[data-symbol="Q1"]')).toHaveClass(/selected/)
  await page.locator('[data-symbol="M1"]').click();await expect(page.getByTestId("selected-id")).toHaveText("component-pump");await expect(page.locator('[data-symbol="M1"]')).toHaveClass(/selected/)
})
test("CAD failure has a bounded visible fallback",async({page})=>{
  await page.route("**/cascadestudio.wasm",route=>route.abort());await page.goto("/");await expect(page.getByTestId("cad-status")).toContainText(/failed.*proxy/i,{timeout:35_000});await expect(page.getByTestId("catalogue-status")).toContainText("Proxy representation used")
})
