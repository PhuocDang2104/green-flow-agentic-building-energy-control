### **Task 1: GreenFlow BIM/Xeokit 3D viewer.**

Current context:  
\- The viewer loads separate Xeokit/XKT files per checkbox/layer.  
\- Existing layers include:  
\- Structural  
\- Electrical  
\- HVAC  
\- Architecture  
\- Spaces / Zones  
\- Architecture view must remain clean and minimal because it is used for architectural inspection.  
\- Structural view should become the most visually complete presentation mode, similar to the original BIM4LCA web preview image:  
\- full building mass visible  
\- correct architectural façade colors  
\- roof/material colors  
\- visible site/base/ground  
\- surrounding context/environment  
\- no excessive transparency  
\- not a ghosted glass model

Goal:  
Refactor the Structural layer behavior into a “Structure Presentation View”.

When the user enables the Structural checkbox:  
1\. Load the structural XKT file as before.  
2\. Also load the architecture shell XKT as a companion visual layer, even if the Architecture checkbox itself is not enabled.  
3\. Also load the site/ground/context XKT if available.  
4\. Apply a dedicated structure presentation style map so the model looks close to the BIM4LCA preview:  
\- walls/floors/slabs opaque light grey  
\- windows and curtain walls semi-transparent cyan/blue  
\- roof dark green or dark grey-green  
\- upper façade / cladding warm brown where applicable  
\- structural beams/columns darker grey  
\- ground/site solid neutral grey  
\- MEP layers hidden unless their own checkbox is enabled  
\- spaces/zones hidden unless their own checkbox is enabled

Important behavior:  
\- Do NOT change the existing Architecture checkbox behavior.  
\- Architecture checkbox should still show the clean architecture-only model.  
\- Structural checkbox should act as a composed view:  
Structural \= structural.xkt \+ architecture shell companion \+ site/context \+ presentation styling.  
\- The companion architecture shell loaded by Structural must not toggle the Architecture checkbox UI state.  
\- If the user turns off Structural, remove/hide:  
\- structural layer  
\- structure companion architecture shell  
\- structure site/context layer  
but do not affect Architecture if the Architecture checkbox was independently enabled.

Layer design:  
Add a concept of \`companionLayers\` or \`presentationLayers\` to the layer config.

Example config shape:

{  
id: "structural",  
label: "Structural",  
group: "TECHNICAL\_SYSTEMS",  
color: "\#9aa3ad",  
xkt: "/models/structure/office\_structural.xkt",  
defaultVisible: false,  
presentationMode: "structure",  
companionLayers: \[  
{  
id: "structure\_arch\_shell",  
xkt: "/models/architecture/office\_architecture.xkt",  
role: "visual\_shell",  
controlledBy: "structural",  
showInLayerPanel: false  
},  
{  
id: "structure\_site\_context",  
xkt: "/models/site/office\_site\_context.xkt",  
role: "site\_context",  
controlledBy: "structural",  
showInLayerPanel: false  
}  
\]  
}

If a separate site/context XKT does not exist:  
\- Search the available BIM4LCA converted models for a site IFC/XKT.  
\- Prefer the architectural site model if available.  
\- If no site model exists, create a lightweight generated context layer in the viewer using Three.js/Xeokit primitives:  
\- rectangular ground slab under the building footprint  
\- neutral grey base plane  
\- optional simple road/sidewalk strips  
\- optional simple low-poly trees or surrounding blocks  
\- Keep generated context subtle and professional.

Styling requirements:  
Implement a structure presentation style map based on IFC entity type and/or object metadata.

Use this target style map:

{  
"IfcSite": {  
"color": \[0.45, 0.45, 0.42\],  
"opacity": 1.0  
},  
"IfcBuildingElementProxy": {  
"color": \[0.72, 0.72, 0.68\],  
"opacity": 1.0  
},  
"IfcSlab": {  
"color": \[0.72, 0.72, 0.68\],  
"opacity": 1.0  
},  
"IfcWall": {  
"color": \[0.80, 0.80, 0.76\],  
"opacity": 1.0  
},  
"IfcWallStandardCase": {  
"color": \[0.80, 0.80, 0.76\],  
"opacity": 1.0  
},  
"IfcCurtainWall": {  
"color": \[0.45, 0.72, 0.78\],  
"opacity": 0.38  
},  
"IfcWindow": {  
"color": \[0.45, 0.78, 0.84\],  
"opacity": 0.38  
},  
"IfcDoor": {  
"color": \[0.12, 0.12, 0.12\],  
"opacity": 1.0  
},  
"IfcRoof": {  
"color": \[0.16, 0.24, 0.12\],  
"opacity": 1.0  
},  
"IfcCovering": {  
"color": \[0.62, 0.34, 0.20\],  
"opacity": 1.0  
},  
"IfcBeam": {  
"color": \[0.38, 0.38, 0.38\],  
"opacity": 0.9  
},  
"IfcColumn": {  
"color": \[0.34, 0.34, 0.34\],  
"opacity": 0.9  
},  
"IfcPlate": {  
"color": \[0.68, 0.70, 0.68\],  
"opacity": 1.0  
},  
"IfcRailing": {  
"color": \[0.18, 0.18, 0.18\],  
"opacity": 1.0  
},  
"IfcStair": {  
"color": \[0.64, 0.64, 0.60\],  
"opacity": 1.0  
},  
"IfcSpace": {  
"visible": false  
},  
"IfcDuctSegment": {  
"visible": false  
},  
"IfcPipeSegment": {  
"visible": false  
},  
"IfcCableCarrierSegment": {  
"visible": false  
},  
"IfcLightFixture": {  
"visible": false  
}  
}

Rendering requirements:  
\- Avoid setting global opacity on the whole model.  
\- Only glass/windows/curtain walls should be transparent.  
\- Spaces/Zones must not be visible in Structural mode unless the Spaces/Zones checkbox is enabled.  
\- HVAC and Electrical must not be visible in Structural mode unless their own checkboxes are enabled.  
\- Enable edge outlines only subtly, not too dark.  
\- Use ambient occlusion / SAO if the current viewer supports it.  
\- Set a camera preset for Structural mode:  
\- isometric 3/4 view  
\- building centered  
\- site visible  
\- not too zoomed in  
\- Use a light background, preferably \#f7fafc or white.  
\- Use shadow or ground contact if available.

UI behavior:  
\- Keep the existing sidebar groups.  
\- Do not add extra visible checkboxes for internal companion layers.  
\- Structural checkbox label can remain “Structural”.  
\- Optional: add small tooltip or subtitle saying “Presentation structure view with architecture shell and site context”.  
\- When Structural is active, visually it should look like a complete building presentation, not a raw structural-only technical model.

Implementation details:  
\- Find the existing layer loading logic for Xeokit/XKT models.  
\- Add support for hidden companion layers controlled by a parent layer.  
\- Ensure companion layers are loaded only once and reused.  
\- Ensure toggling Structural on/off does not duplicate models.  
\- Ensure toggling Architecture independently still works correctly.  
\- If both Structural and Architecture are enabled:  
\- do not double-render the same architecture model if possible  
\- either share the architecture model instance or keep separate IDs with synchronized visibility  
\- avoid z-fighting  
\- If duplicate loading is unavoidable, make the structural companion architecture shell hidden when the main Architecture layer is visible.

Acceptance criteria:  
1\. Architecture checkbox alone still shows the clean architecture model.  
2\. Structural checkbox alone shows a complete colored building with:  
\- façade  
\- windows  
\- roof  
\- structural frame  
\- ground/site/context  
3\. Structural view no longer appears washed out, fully transparent, or ghost-like.  
4\. Spaces/Zones are hidden unless explicitly enabled.  
5\. HVAC/Electrical are hidden unless explicitly enabled.  
6\. Turning Structural off removes its companion shell and site context without changing the Architecture checkbox state.  
7\. The first camera view of Structural mode resembles the BIM4LCA reference preview: full building, clean isometric angle, visible base/site, readable material colors. Tự tô màu và enhance texture của những cảnh xung quanh cho đẹp mắt

Please implement this with minimal changes to the current architecture, using the existing Xeokit loading and layer state management patterns.   
→ **Structural không còn là “raw structural layer” nữa, mà là “presentation mode” gồm Structural \+ Architecture shell \+ Site context \+ material styling.** Còn Architecture riêng vẫn giữ sạch để soi kiến trúc. 

### **Task 2: Run Optimization logging UI enhancing**

Inspect ImageC:\\Users\\ADMIN\\Desktop\\greenflow-agentic-building-energy\\web\\public\\assets\\landing\\chatbot\\optimization\_agents\_logging.png carefully as the exact visual reference. Upgrade the current UI in web to match Image 1 as closely as possible, without changing the overall content, order, or layout logic.

Keep the chatbot runtime logging structure, but improve it into a polished vertical execution timeline. Add a clean white main card with a subtle border and soft radius. Make the left timeline clearer with a thin vertical line and consistent green check nodes. Use stronger typography hierarchy: bold step titles, smaller muted descriptions, and consistent latency chips aligned to the right.

Make Prediction Agent the active highlighted step, using a very light teal background, teal border, and clear rounded card like Image 1\. Inside it, create a clean prediction detail card showing Building load 855.72 kW → 956.19 kW, a red “peak high” badge, top affected zone/device bars, and a forecasted building load chart.

Improve Building Semantic Agent by keeping the BIM preview image inside a clean bordered image card. Improve Control Agent by turning the candidate actions into compact approval rows with warning icon, action name, saving value, approval\_required label, and Approve / Reject buttons on the right. Keep Policy Engine, Execution / Approval, Response Composer, and Audit Logger as compact timeline logs.

Make the final summary box cleaner with light teal background, better padding, readable text, and subtle border. Do not redesign from scratch, do not add unrelated elements, and do not change the GreenFlow color direction. The final UI should look sharper, more professional, more readable, and very close to Image 1\.

### **Task 3: xóa bỏ, điều chỉnh UI lặt vặt**

\- bỏ nút Go live   
\- Table Zone state ở tab đầu cho height ngắn lại (vừa đủ thấy phần Zone và Weather at replay time trong cùng 1 view)

\- Đỏi: Demo Manager

orangeangiang@gmail.com

thành Facility Manager  
[vituonglaixanh@vingroup.net](mailto:vituonglaixanh@vingroup.net) và logo user lấy ở: C:\\Users\\ADMIN\\Desktop\\greenflow-agentic-building-energy\\web\\public\\assets\\landing\\user\_logo.png

\- tab 4:  
\+ bỏ: Predictive MPC replay · building with AI vs without AI

\+ What-if Analysis

Compare measured baseline with the precomputed predictive MPC replay.  
Đổi thành cái gì đó hợp lý hơn với Validation Experiment (Elnino 2024 \- Hanoi)

\- Logo của chatbot: Building Copilot đổi thành C:\\Users\\ADMIN\\Desktop\\greenflow-agentic-building-energy\\web\\public\\assets\\landing\\AI-greenflow\_logo.png  
