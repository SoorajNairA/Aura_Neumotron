import {Serial} from "./hardware";
import {agreement,fanAgreement,history,LIVE_LABEL,telemetryInputs,telemetryOutputs} from "./live";
import {outputText} from "./GenericSimulation";
import {FirmwareInfo} from "./SimulationPanel";

export function LiveBoard({firmware,serial}:{firmware:FirmwareInfo;serial:Serial}){
 const {lines,wrongRevision,port,fake}=serial.state,ios=(firmware.ios||[]).filter(io=>io.supported);
 const latest=[...lines].reverse().find(line=>line.telemetry)?.telemetry;
 const generic=firmware.kind==="generic";
 const disagree=generic?agreement(history(lines,ios),firmware.rules||[],ios).disagree:fanAgreement(lines,firmware.tOnC??26,firmware.tOffC??24)?[]:["fan"];
 const inputs=latest&&generic?telemetryInputs(latest,ios):{},outputs=latest&&generic?telemetryOutputs(latest,ios):{};
 return <aside className="simulation-panel" data-testid="live-board">
  <small>LIVE BOARD · {port}{fake?" · FAKE BOARD (TEST)":""}</small>
  <p className="sim-label" data-testid="live-label">{LIVE_LABEL}</p>
  {wrongRevision&&<p className="tone-warn" role="alert">Board runs revision {wrongRevision.board}, not the current design ({wrongRevision.current}). Upload to update it.</p>}
  {!latest&&<p className="sim-note">Waiting for telemetry…</p>}
  {latest&&generic&&<ul className="sim-outputs">
   {ios.filter(io=>io.role==="input").map(io=><li key={io.id} className="sim-state"><span data-testid={`live-${io.id}`}>{io.id} <b>{inputs[io.id]===null||inputs[io.id]===undefined?"sensor fault":typeof inputs[io.id]==="boolean"?(inputs[io.id]?"ON":"OFF"):`${inputs[io.id]} ${io.unit}`}</b></span><span>{io.name}</span></li>)}
   {ios.filter(io=>io.role==="output").map(io=><li key={io.id} className={`sim-state ${Number(outputs[io.id])>0?"on":"off"}`}><span data-testid={`live-${io.id}`}>{io.id} <b>{outputText(outputs[io.id])}</b></span><span>{io.name}</span></li>)}</ul>}
  {latest&&!generic&&<div className={`sim-state ${Number(latest.fan)>0?"on":"off"}`}><span data-testid="live-fan">Fan <b>{Number(latest.fan)>0?"ON":"OFF"}</b></span><span>{latest.t_c===null?"sensor fault":`${latest.t_c} °C`}</span></div>}
  {disagree.length>0&&<ul className="sim-warnings" role="alert" data-testid="live-disagree">{disagree.map(id=><li key={id}>Board output disagrees with the rule for {id}</li>)}</ul>}
  <p className="sim-note">3D follows the values the board reports.</p>
 </aside>;
}
