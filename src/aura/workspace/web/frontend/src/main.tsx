import { createRoot } from "react-dom/client";
import "./styles.css";
import "./compatibility.css";
import { WorkspaceApp } from "./WorkspaceApp";

createRoot(document.getElementById("root")!).render(<WorkspaceApp />);
