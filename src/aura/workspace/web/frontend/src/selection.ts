export type SelectionSource="3d"|"schematic"|"hierarchy"|"narration"|"evidence"|"programmatic";
export type SelectionState={selectedSemanticId:string|null;hoveredSemanticId:string|null;auraFocusSemanticIds:string[]};
export type SelectionEvent={source:SelectionSource;semanticId:string|null;previous:string|null;next:string|null;timestamp:number};

export class SelectionStore {
  private state:SelectionState={selectedSemanticId:null,hoveredSemanticId:null,auraFocusSemanticIds:[]};
  private listeners=new Set<(state:SelectionState,event:SelectionEvent)=>void>();
  private events:SelectionEvent[]=[];
  get snapshot(){return this.state}
  get subscriberCount(){return this.listeners.size}
  get eventCount(){return this.events.length}
  select(semanticId:string|null,source:SelectionSource){
    const previous=this.state.selectedSemanticId;
    if(previous===semanticId)return;
    this.state={...this.state,selectedSemanticId:semanticId};
    const event={source,semanticId,previous,next:semanticId,timestamp:Date.now()};
    this.events.push(event);this.emit(event);
  }
  hover(semanticId:string|null){this.state={...this.state,hoveredSemanticId:semanticId}}
  focus(ids:string[]){this.state={...this.state,auraFocusSemanticIds:[...new Set(ids)]}}
  reset(){this.state={selectedSemanticId:null,hoveredSemanticId:null,auraFocusSemanticIds:[]}}
  subscribe(listener:(state:SelectionState,event:SelectionEvent)=>void){this.listeners.add(listener);return()=>this.listeners.delete(listener)}
  private emit(event:SelectionEvent){for(const listener of this.listeners)listener(this.state,event)}
}
