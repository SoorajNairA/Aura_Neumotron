import {describe,expect,it} from "vitest";
import {dateStamp,exportName,filenameFromDisposition,importErrorMessage,localCopyName,slugify} from "./projectFiles";

describe("project file helpers",()=>{
 it("slugifies titles",()=>{expect(slugify("Design a Desk Fan!")).toBe("design-a-desk-fan");expect(slugify("")).toBe("project")});
 it("reads the filename from Content-Disposition",()=>{
  expect(filenameFromDisposition('attachment; filename="aura-fan.zip"')).toBe("aura-fan.zip");
  expect(filenameFromDisposition("attachment; filename=aura-fan.zip")).toBe("aura-fan.zip");
  expect(filenameFromDisposition(null)).toBeUndefined();
  expect(filenameFromDisposition('attachment; filename="../evil.zip"')).toBe(".._evil.zip");
 });
 it("falls back to a slug of the title",()=>{expect(exportName(null,"Desk Fan")).toBe("aura-desk-fan.zip")});
 it("names local copies with the date",()=>{
  expect(dateStamp(new Date(2026,9,5))).toBe("2026-10-05");
  expect(localCopyName("aura-fan.zip",new Date(2026,9,29))).toBe("aura-fan-local-2026-10-29.zip");
 });
 it("shows the server message for import errors",()=>{
  expect(importErrorMessage({detail:{code:"UNSUPPORTED_VERSION",message:"Newer AURA needed."}},400)).toBe("Newer AURA needed.");
  expect(importErrorMessage(undefined,500)).toBe("The project could not be imported.");
 });
});
