const {app,BrowserWindow,ipcMain,shell}=require("electron");
const path=require("node:path");

const apiUrl=(process.env.AURA_API_URL||"http://127.0.0.1:8765").replace(/\/$/,"");
const wsUrl=(process.env.AURA_WS_URL||apiUrl.replace(/^http/,"ws")).replace(/\/$/,"");
let mainWindow;
function createWindow(){
 mainWindow=new BrowserWindow({width:1600,height:960,minWidth:1080,minHeight:680,backgroundColor:"#02070d",show:false,title:"AURA Engineering Workspace",webPreferences:{preload:path.join(__dirname,"preload.cjs"),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}});
 mainWindow.removeMenu();mainWindow.webContents.setWindowOpenHandler(({url})=>{if(/^https:\/\//.test(url))shell.openExternal(url);return{action:"deny"}});
 mainWindow.webContents.on("will-navigate",(event,url)=>{if(!url.startsWith(apiUrl))event.preventDefault()});
 mainWindow.once("ready-to-show",()=>mainWindow.show());
 mainWindow.webContents.once("did-finish-load",()=>{if(process.argv.includes("--smoke")){console.log("AURA_ELECTRON_SMOKE_PASS");setTimeout(()=>app.quit(),250)}});
 const projectId=process.env.AURA_PROJECT_ID;
 const startUrl=projectId?`${apiUrl}/?projectId=${encodeURIComponent(projectId)}`:apiUrl;
 mainWindow.loadURL(startUrl).catch(()=>mainWindow.loadFile(path.join(__dirname,"offline.html")));
}
ipcMain.handle("aura:window",(_event,action)=>{if(!mainWindow)return false;if(action==="minimize")mainWindow.minimize();else if(action==="maximize")mainWindow.isMaximized()?mainWindow.unmaximize():mainWindow.maximize();else if(action==="close")mainWindow.close();else return false;return true});
app.whenReady().then(createWindow);app.on("window-all-closed",()=>app.quit());
