export type Fact={value:any;unit:string|null;evidenceId:string;qualifier:string};
export type CatalogueItem={componentDefinitionId:string;family:string;manufacturer:string;partNumber:string;
 properties:Record<string,Fact>;interfaces:string[];evidenceIds:string[];price:{usd:number;source:string;retrieved:string}|null};

export function filterParts(items:CatalogueItem[],query:string,family:string|null):CatalogueItem[]{
 const q=query.trim().toLowerCase();
 return items.filter(i=>(!family||i.family===family)&&(!q||[i.partNumber,i.manufacturer,i.family,i.componentDefinitionId].some(v=>v.toLowerCase().includes(q))));
}

export const priceLabel=(item:Pick<CatalogueItem,"price">)=>item.price?`$${item.price.usd.toFixed(2)} (retrieved ${item.price.retrieved})`:"price unavailable";

export function factLabel(fact:Fact|undefined):string|null{
 if(!fact)return null;
 const value=Array.isArray(fact.value)?fact.value.join(fact.unit==="mm"?" × ":"–"):String(fact.value);
 return `${value}${fact.unit?` ${fact.unit}`:""}`;
}
