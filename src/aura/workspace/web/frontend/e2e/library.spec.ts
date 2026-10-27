import {expect,test,Page} from "@playwright/test";
import {mock} from "./fanFixture";

const fact=(value:any,unit:string|null)=>({value,unit,evidenceId:"e",qualifier:"rated"});
const part=(componentDefinitionId:string,family:string,partNumber:string,price:any=null)=>({componentDefinitionId,family,manufacturer:"Generic",partNumber,
 properties:{supply_voltage_range:fact([3,5.5],"V"),dimensions:fact([20,10,5],"mm")},interfaces:["power","ground","signal"],evidenceIds:["e"],price});
export const catalogue=[part("ds18b20-module","temperature_sensor","DS18B20 module",{usd:3.95,source:"https://example.com",retrieved:"2026-10-27"}),
 part("dc-fan-5v","fan","5 V brushless fan"),part("resistor-4k7","resistor","4.7 kΩ resistor",{usd:0.1,source:"https://example.com",retrieved:"2026-10-27"})];

export async function openLibrary(page:Page){
 await mock(page);
 await page.route("**/api/catalogue",r=>r.fulfill({json:catalogue}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Open component library"}).click();
 await expect(page.getByRole("dialog",{name:"Component library"})).toBeVisible();
}

test("library opens, searches, filters and labels unpriced parts",async({page})=>{
 await openLibrary(page);
 await expect(page.getByTestId("library-row")).toHaveCount(3);
 await page.getByLabel("Search parts").fill("ds18");
 await expect(page.getByTestId("library-row")).toHaveCount(1);
 await expect(page.getByTestId("library-row")).toContainText("$3.95 (retrieved 2026-10-27)");
 await page.getByLabel("Search parts").fill("");
 await page.getByRole("group",{name:"Filter by family"}).getByRole("button",{name:"fan",exact:true}).click();
 await expect(page.getByTestId("library-row")).toHaveCount(1);
 await expect(page.getByTestId("library-row")).toContainText("price unavailable");
 await page.getByLabel("Search parts").press("Escape");
 await expect(page.getByRole("dialog",{name:"Component library"})).toHaveCount(0);
 await expect(page.getByRole("button",{name:"Open component library"})).toBeFocused();
});
