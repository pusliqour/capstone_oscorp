import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

import "./index.css";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {import.meta.env.VITE_TEAM_DEMO === "true" && (
      <aside role="note" style={{position:"fixed",bottom:0,left:0,right:0,zIndex:10000,padding:"6px 16px",background:"#fff4d6",color:"#553c10",fontSize:12,textAlign:"center"}}>
        Team demo · Imported data source awaiting confirmation · Historical data, not live sales
      </aside>
    )}
    <App />
  </React.StrictMode>
);

