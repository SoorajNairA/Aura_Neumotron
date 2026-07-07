import {describe,expect,it,vi} from "vitest";
import {SelectionStore} from "./selection";

describe("authoritative selection",()=>{
 it("keeps the final intent stable after twenty rapid selections",()=>{vi.useFakeTimers();const store=new SelectionStore(),seen:string[]=[];const stop=store.subscribe(s=>seen.push(s.selectedSemanticId!));const subscribers=store.subscriberCount;for(let i=0;i<20;i++)store.select(`component-${i%5}`,"3d");expect(store.snapshot.selectedSemanticId).toBe("component-4");vi.advanceTimersByTime(5000);expect(store.snapshot.selectedSemanticId).toBe("component-4");expect(store.subscriberCount).toBe(subscribers);expect(store.eventCount).toBeLessThanOrEqual(20);expect(seen.at(-1)).toBe("component-4");stop();expect(store.subscriberCount).toBe(0);vi.useRealTimers()});
 it("separates hover and narration focus from user selection",()=>{const store=new SelectionStore();store.select("component-servo","schematic");store.hover("component-controller");store.focus(["component-pump"]);expect(store.snapshot).toEqual({selectedSemanticId:"component-servo",hoveredSemanticId:"component-controller",auraFocusSemanticIds:["component-pump"]})});
 it("alternating surfaces produces one bounded event per changed intent",()=>{const store=new SelectionStore();for(const [id,source] of [["a","3d"],["b","schematic"],["c","hierarchy"],["a","3d"],["b","schematic"]] as const)store.select(id,source);expect(store.snapshot.selectedSemanticId).toBe("b");expect(store.eventCount).toBe(5)});
});
