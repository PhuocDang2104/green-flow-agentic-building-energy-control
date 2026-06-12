# **GreenFlow | Cấu trúc data, logic dựng 3D View & Mapping IFC Digital Twin Building bằng xeokit**

## **1\. Mục tiêu**

GreenFlow sử dụng bộ dữ liệu BIM/IFC của tòa nhà văn phòng để dựng một **semantic digital twin 3D** có thể hiển thị kiến trúc, không gian, hệ HVAC, hệ điện, kết cấu, terrain và các biến vận hành như nhiệt độ, occupancy, cooling load, lighting load, comfort risk, peak risk hoặc anomaly.

Trong GreenFlow, 3D viewer không chỉ là nơi “xem mô hình BIM”, mà là giao diện vận hành trung tâm của toàn bộ hệ thống.

Mục tiêu chính:

* Hiểu cấu trúc tòa nhà theo tầng, phòng, thermal zone và thiết bị.  
* Hiển thị nhiều lớp BIM chồng lên nhau: Architecture, Spaces/Zones, HVAC, Electrical, Structural, Terrain.  
* Cho phép click trực tiếp vào từng object 3D để inspect metadata, state và quan hệ graph.  
* Gắn dữ liệu động theo thời gian vào từng room, zone hoặc device.  
* Hiển thị heatmap năng lượng, comfort, occupancy, action và anomaly ngay trên mô hình 3D.  
* Sinh input cho EnergyPlus để mô phỏng baseline năng lượng.  
* Lưu semantic context vào GraphDB để phục vụ GraphRAG, chatbot agent và explainable query.

Stack 3D chính được chọn:

xeokit SDK  
\+ XKT geometry format  
\+ XKTLoaderPlugin  
\+ xeokit Entity / MetaObject mapping  
\+ WebSocket dynamic overlay

Pipeline tổng thể:

5 IFC files  
→ IFC parser  
→ normalized JSON  
→ XKT 3D assets  
→ xeokit Viewer  
→ PostgreSQL / PostGIS / TimescaleDB / GraphDB / Object Storage  
→ EnergyPlus baseline simulation  
→ 3D dashboard \+ chatbot agent \+ control/anomaly view

Nguyên tắc thiết kế:

IFC \= source data  
XKT \= optimized web 3D asset  
xeokit \= BIM viewer engine  
Database \= semantic \+ state source of truth  
EnergyPlus \= simulation engine  
GraphDB \= relationship reasoning layer

---

## **2\. Lý do chọn xeokit làm 3D stack**

GreenFlow cần một viewer tối ưu cho BIM/AEC, không chỉ một viewer 3D đơn giản. Vì vậy, xeokit là lựa chọn phù hợp cho MVP và cả hướng mở rộng.

xeokit phù hợp với GreenFlow vì:

* Tối ưu cho BIM và AEC model có nhiều object.  
* Hỗ trợ load XKT, định dạng compact cho BIM web viewer.  
* Có sẵn hệ object/entity để click, select, hide/show, highlight, x-ray, opacity và colorize object.  
* Có thể giữ metadata BIM theo object.  
* Phù hợp với mô hình nhiều discipline: Architecture, HVAC, Electrical, Structural, Terrain.  
* Phù hợp với dashboard digital twin cần update state theo object ID.  
* Có thể tích hợp tốt với Next.js frontend, FastAPI backend và WebSocket state update.  
* Cho phép xây dựng viewer tùy chỉnh thay vì dùng viewer đóng gói cố định.

Trong GreenFlow, xeokit đóng vai trò:

xeokit Viewer  
→ load XKT assets  
→ quản lý object/entity  
→ hiển thị BIM layer  
→ bắt sự kiện click/pick object  
→ đổi màu/opacity/highlight theo realtime state  
→ phục vụ 3D digital twin dashboard

---

## **3\. Vai trò từng file IFC**

Bộ dữ liệu BIM gồm 5 nhóm chính:

### **3.1. ARCH As-Built**

Nguồn chính cho:

* building geometry  
* floors  
* rooms  
* IfcSpace  
* walls  
* windows  
* doors  
* slabs  
* roofs  
* envelope  
* room boundary  
* thermal zone source

Trong GreenFlow, **ARCH As-Built là source of truth** cho building geometry, rooms, spaces, thermal zoning và envelope. Lý do là file này có đầy đủ thông tin không gian, floor, wall, slab, window, door và boundary để dựng thermal zone và mapping sang EnergyPlus.

### **3.2. HVAC BuildingPermit**

Nguồn chính cho:

* air terminal  
* diffuser  
* cooled beam  
* duct  
* pipe  
* valve  
* fan  
* pump  
* coil  
* chiller nếu có  
* HVAC layer  
* action/control target

HVAC IFC không phải source chính cho zoning. Nó được dùng để overlay thiết bị, gán thiết bị vào room/zone bằng spatial join và phục vụ graph query.

### **3.3. ELE BuildingPermit**

Nguồn chính cho:

* light fixture  
* outlet  
* electrical board  
* cable tray  
* cable fitting  
* electrical layer  
* lighting/plug-load approximation

ELE IFC được dùng cho 3D electrical view, EnergyPlus lighting/equipment approximation và semantic graph.

### **3.4. STRUCTURAL BuildingPermit**

Nguồn phụ cho:

* slab  
* beam  
* column  
* structural wall  
* roof  
* material  
* mass  
* LCA  
* structural view

Structural IFC không cần đưa toàn bộ object vào EnergyPlus. Nó chủ yếu phục vụ structural visualization, material/mass reference, embodied carbon và internal mass approximation.

### **3.5. Terrain / Site**

Nguồn cho:

* ground  
* outdoor area  
* parking  
* ramp  
* surrounding context  
* site visualization  
* shading reference

Terrain không phải nguồn chính cho zoning. Nó dùng để tạo context 3D và có thể dùng làm external shading trong phase sau.

---

## **4\. Nguyên tắc cốt lõi khi dựng 3D View bằng xeokit**

Nguyên tắc quan trọng nhất:

3D geometry \= static XKT layer  
Realtime/simulation variables \= dynamic overlay

Không render lại IFC mỗi lần nhiệt độ, occupancy, comfort risk hoặc cooling load thay đổi. IFC nặng, nhiều metadata và không phù hợp để xử lý trực tiếp mỗi lần frontend update.

Thay vào đó, GreenFlow dùng pipeline:

IFC  
→ parse metadata  
→ convert geometry sang XKT  
→ lưu XKT asset vào Object Storage  
→ lưu mapping giữa xeokit object\_id và entity\_id  
→ frontend load XKT một lần bằng xeokit  
→ realtime/simulation state được update bằng API/WebSocket  
→ frontend đổi màu, opacity, label, icon, highlight hoặc x-ray object

Ví dụ asset:

ARCH IFC      → arch\_shell.xkt  
IfcSpace      → spaces.xkt  
ThermalZone   → thermal\_zones.xkt  
HVAC IFC      → hvac\_equipment.xkt  
HVAC Duct     → hvac\_ducts.xkt  
HVAC Pipe     → hvac\_pipes.xkt  
ELE IFC       → electrical\_equipment.xkt  
STRUCT IFC    → structural\_elements.xkt  
Terrain IFC   → terrain.xkt

Frontend chỉ cần bật/tắt layer bằng checkbox:

\[ \] Architecture  
\[ \] Spaces / Zones  
\[ \] HVAC  
\[ \] Electrical  
\[ \] Structural  
\[ \] Terrain  
\[ \] Energy  
\[ \] Comfort Risk  
\[ \] Occupancy  
\[ \] Action / Anomaly

Trong xeokit, mỗi object nên có một ID ổn định. ID này là cầu nối giữa viewer, database, EnergyPlus output và GraphDB.

---

## **5\. Kiến trúc xeokit Viewer trong GreenFlow**

### **5.1. Thành phần frontend**

Frontend đề xuất:

Next.js  
\+ xeokit-sdk  
\+ XKTLoaderPlugin  
\+ custom dashboard UI  
\+ WebSocket state update  
\+ object inspection panel  
\+ layer control panel  
\+ view mode control

Các module frontend chính:

/components/GreenFlowViewer  
/components/LayerPanel  
/components/ObjectInspector  
/components/FloorSelector  
/components/ViewModeToolbar  
/components/MetricLegend  
/components/ActionPanel  
/components/AgentPanel

### **5.2. Thành phần xeokit chính**

Trong GreenFlow, xeokit Viewer quản lý:

* Scene  
* Entity  
* Object visibility  
* Object opacity  
* Object colorize  
* Object highlight  
* Object x-ray  
* Object selection  
* Camera  
* Section planes  
* Metadata lookup  
* Picking/clicking object

Luồng viewer:

Load XKT assets  
→ register model\_id  
→ register object\_id list by layer  
→ attach metadata  
→ load mapping JSON  
→ wait for user interaction/state update  
→ update visual state

### **5.3. Cấu trúc viewer state**

Frontend nên giữ viewer state riêng:

{  
  "building\_id": "office\_demo\_001",  
  "active\_floor\_id": "level\_03",  
  "active\_view\_mode": "comfort",  
  "selected\_entity\_id": "zone\_level03\_openoffice\_east",  
  "visible\_layers": {  
    "architecture": true,  
    "spaces": true,  
    "thermal\_zones": true,  
    "hvac": false,  
    "electrical": false,  
    "structural": false,  
    "terrain": true  
  },  
  "active\_metric": "comfort\_risk"  
}

---

## **6\. Cấu trúc XKT asset đề xuất**

GreenFlow không nên export toàn bộ building thành một file duy nhất. Nên tách asset theo discipline và theo mục đích hiển thị.

Cấu trúc thư mục:

/assets/buildings/office\_demo\_001/  
  xkt/  
    arch\_shell.xkt  
    arch\_floors.xkt  
    arch\_envelope.xkt  
    spaces.xkt  
    thermal\_zones.xkt  
    hvac\_equipment.xkt  
    hvac\_ducts.xkt  
    hvac\_pipes.xkt  
    electrical\_lights.xkt  
    electrical\_outlets.xkt  
    electrical\_boards.xkt  
    structural\_elements.xkt  
    terrain.xkt

  metadata/  
    arch\_metadata.json  
    spaces\_metadata.json  
    thermal\_zones\_metadata.json  
    hvac\_metadata.json  
    electrical\_metadata.json  
    structural\_metadata.json  
    terrain\_metadata.json

  mapping/  
    xeokit\_object\_map.json  
    geometry\_asset\_map.json  
    zone\_equipment\_map.json  
    floor\_object\_index.json  
    layer\_object\_index.json

### **6.1. XKT manifest**

Nên có một file manifest để frontend biết phải load asset nào.

{  
  "building\_id": "office\_demo\_001",  
  "viewer\_stack": "xeokit",  
  "geometry\_format": "xkt",  
  "assets": \[  
    {  
      "asset\_id": "arch\_shell",  
      "layer": "architecture",  
      "model\_id": "model\_arch\_shell",  
      "src": "/assets/buildings/office\_demo\_001/xkt/arch\_shell.xkt",  
      "metadata\_src": "/assets/buildings/office\_demo\_001/metadata/arch\_metadata.json",  
      "default\_visible": true  
    },  
    {  
      "asset\_id": "thermal\_zones",  
      "layer": "thermal\_zones",  
      "model\_id": "model\_thermal\_zones",  
      "src": "/assets/buildings/office\_demo\_001/xkt/thermal\_zones.xkt",  
      "metadata\_src": "/assets/buildings/office\_demo\_001/metadata/thermal\_zones\_metadata.json",  
      "default\_visible": true  
    },  
    {  
      "asset\_id": "hvac\_equipment",  
      "layer": "hvac",  
      "model\_id": "model\_hvac\_equipment",  
      "src": "/assets/buildings/office\_demo\_001/xkt/hvac\_equipment.xkt",  
      "metadata\_src": "/assets/buildings/office\_demo\_001/metadata/hvac\_metadata.json",  
      "default\_visible": false  
    }  
  \]  
}

---

## **7\. Cấu trúc layer 3D đề xuất**

## **7.1. Architecture Layer**

Nguồn: ARCH As-Built.

Hiển thị:

* wall  
* slab  
* floor  
* roof  
* ceiling  
* door  
* window  
* curtain wall  
* envelope  
* room boundary reference

File XKT xuất ra:

arch\_shell.xkt  
arch\_floors.xkt  
arch\_envelope.xkt

Vai trò:

* Dựng hình chính của tòa nhà.  
* Làm nền cho các layer khác.  
* Cung cấp geometry nguồn cho EnergyPlus.  
* Cho phép inspect wall/window/slab/material.  
* Cho phép x-ray hoặc giảm opacity khi xem HVAC/Electrical.

Visual rule:

Architecture View:  
architecture visible \= true  
spaces visible \= optional  
hvac visible \= false  
electrical visible \= false  
structural visible \= optional

HVAC View:  
architecture opacity \= 0.15–0.3  
hvac visible \= true

Energy View:  
architecture opacity \= 0.1–0.2  
thermal\_zones visible \= true

---

## **7.2. Space / Zone Layer**

Nguồn: IfcSpace trong ARCH As-Built.

Hiển thị:

* room volume  
* room footprint  
* thermal zone volume  
* floor zoning  
* zone heatmap overlay

File XKT xuất ra:

spaces.xkt  
thermal\_zones.xkt

Đây là layer quan trọng nhất cho dashboard năng lượng.

Mỗi zone phải có ID ổn định:

{  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "entity\_type": "ThermalZone",  
  "floor\_id": "level\_03",  
  "source": "ARCH\_AsBuilt",  
  "ifc\_global\_id": "2H9sKxxxx",  
  "xeokit\_object\_id": "zone\_level03\_openoffice\_east",  
  "layer": "thermal\_zones"  
}

Vai trò:

* Gắn temperature, humidity, occupancy, energy, comfort risk.  
* Là object chính để colorize theo Energy View.  
* Là object chính để user click và hỏi chatbot.  
* Là node trung tâm trong semantic graph.  
* Là đơn vị mapping chính với EnergyPlus output.

---

## **7.3. HVAC Layer**

Nguồn: HVAC BuildingPermit.

Hiển thị:

* air terminal  
* diffuser  
* cooled beam  
* duct  
* pipe  
* valve  
* fan  
* pump  
* coil  
* chiller nếu có

File XKT xuất ra:

hvac\_equipment.xkt  
hvac\_ducts.xkt  
hvac\_pipes.xkt

Vai trò MVP:

* Visualize hệ HVAC.  
* Xác định action target.  
* Map terminal/equipment vào thermal zone.  
* Cho phép click vào thiết bị để xem trạng thái.  
* Hỗ trợ chatbot trả lời thiết bị nào đang phục vụ zone nào.  
* Hỗ trợ explainable control/action.

Không nên đưa toàn bộ duct/pipe chi tiết vào EnergyPlus phase 1\. HVAC IFC trong MVP chủ yếu phục vụ visualization, mapping, graph và action target.

Ví dụ metadata air terminal:

{  
  "entity\_id": "airterminal\_00451",  
  "entity\_type": "AirTerminal",  
  "ifc\_class": "IfcAirTerminal",  
  "ifc\_global\_id": "3Df9Axxxx",  
  "xeokit\_object\_id": "hvac\_airterminal\_00451",  
  "floor\_id": "level\_03",  
  "assigned\_zone\_id": "zone\_level03\_openoffice\_east",  
  "source\_file": "HVAC\_BuildingPermit",  
  "layer": "hvac"  
}

---

## **7.4. Electrical Layer**

Nguồn: ELE BuildingPermit.

Hiển thị:

* light fixture  
* outlet  
* electrical board  
* cable tray  
* cable fitting

File XKT xuất ra:

electrical\_lights.xkt  
electrical\_outlets.xkt  
electrical\_boards.xkt  
electrical\_cable\_trays.xkt

Vai trò:

* Xem lighting layout.  
* Xem outlet và plug load.  
* Xem electrical board và peak warning.  
* Map light fixture và outlet vào room/zone.  
* Dùng lighting/equipment approximation cho EnergyPlus.  
* Dùng cable tray/cable fitting cho visualization và graph.

Trong EnergyPlus MVP:

IfcLightFixture → Lights  
IfcOutlet → ElectricEquipment  
IfcElectricDistributionBoard → meter/graph metadata  
IfcCableCarrierSegment → 3D view only

---

## **7.5. Structural Layer**

Nguồn: STRUCTURAL BuildingPermit.

Hiển thị:

* slab  
* beam  
* column  
* structural wall  
* roof  
* material/mass

File XKT xuất ra:

structural\_elements.xkt  
structural\_mass.xkt

Vai trò:

* Xem kết cấu.  
* Bổ sung material/mass.  
* Hỗ trợ LCA/embodied carbon.  
* Kiểm tra building mass.  
* Bổ sung thermal mass approximation.

Không cần mô phỏng từng beam/column trong EnergyPlus. Chỉ nên dùng structural data để tổng hợp material, mass hoặc internal mass.

---

## **7.6. Terrain Layer**

Nguồn: Terrain / Site.

Hiển thị:

* ground  
* outdoor area  
* parking  
* ramp  
* surrounding context  
* shading reference

File XKT xuất ra:

terrain.xkt  
site\_context.xkt

Vai trò:

* Tạo context 3D.  
* Hiển thị site xung quanh building.  
* Hỗ trợ external shading trong phase sau.  
* Không dùng làm source chính cho zoning.

---

## **8\. Entity ID, xeokit Object ID và Mapping**

Muốn 3D view thay đổi theo biến realtime, mỗi object trong xeokit phải map về một entity trong database.

Trong GreenFlow, nên tách rõ:

xeokit\_object\_id \= ID object trong viewer  
ifc\_global\_id \= ID gốc từ IFC  
entity\_id \= ID chuẩn trong database/GraphDB  
entity\_type \= loại entity chuẩn của GreenFlow

Mapping chuẩn:

xeokit\_object\_id  
→ ifc\_global\_id  
→ entity\_id  
→ entity\_type  
→ floor\_id  
→ room\_id  
→ zone\_id  
→ layer  
→ model\_id  
→ asset\_url

Ví dụ một thermal zone:

{  
  "xeokit\_object\_id": "zone\_level03\_openoffice\_east",  
  "ifc\_global\_id": "2H9sKxxxx",  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "entity\_type": "ThermalZone",  
  "floor\_id": "level\_03",  
  "room\_ids": \[  
    "room\_03\_201",  
    "room\_03\_202",  
    "room\_03\_203"  
  \],  
  "layer": "thermal\_zones",  
  "model\_id": "model\_thermal\_zones",  
  "asset\_id": "thermal\_zones"  
}

Ví dụ một air terminal:

{  
  "xeokit\_object\_id": "hvac\_airterminal\_00451",  
  "ifc\_global\_id": "3Df9Axxxx",  
  "entity\_id": "airterminal\_00451",  
  "entity\_type": "AirTerminal",  
  "floor\_id": "level\_03",  
  "assigned\_room\_id": "room\_03\_215",  
  "assigned\_zone\_id": "zone\_level03\_openoffice\_east",  
  "source\_file": "HVAC\_BuildingPermit",  
  "layer": "hvac",  
  "model\_id": "model\_hvac\_equipment"  
}

Frontend click object:

User click object trong xeokit  
→ lấy xeokit\_object\_id  
→ tra xeokit\_object\_map.json  
→ lấy entity\_id  
→ gọi API entity/state/neighbors  
→ hiển thị Object Inspector  
→ highlight các object liên quan

API gọi từ frontend:

GET /api/entities/{entity\_id}  
GET /api/entities/{entity\_id}/state  
GET /api/entities/{entity\_id}/history  
GET /api/entities/{entity\_id}/neighbors  
GET /api/entities/{entity\_id}/served-by  
GET /api/entities/{entity\_id}/serves

---

## **9\. Metadata trong xeokit**

Trong GreenFlow, metadata là phần bắt buộc. Viewer không chỉ cần geometry mà còn cần biết object đó là gì.

Metadata cần có cho mỗi object:

{  
  "id": "zone\_level03\_openoffice\_east",  
  "name": "Level 03 Open Office East",  
  "type": "ThermalZone",  
  "ifc\_type": "IfcSpaceGroup",  
  "ifc\_global\_id": "2H9sKxxxx",  
  "floor\_id": "level\_03",  
  "layer": "thermal\_zones",  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "properties": {  
    "area\_m2": 183.4,  
    "volume\_m3": 550.2,  
    "usage": "OpenOffice",  
    "orientation": "East",  
    "source": "ARCH\_AsBuilt"  
  }  
}

Frontend Object Inspector nên hiển thị:

Name  
Entity Type  
IFC Type  
Floor  
Room/Zone  
Area/Volume  
Current State  
Connected Devices  
EnergyPlus Baseline  
Graph Neighbors  
Available Actions

---

## **10\. Normalized Data cần sinh ra**

Sau khi parse IFC, không nên đưa trực tiếp IFC vào backend. Cần sinh một lớp dữ liệu trung gian sạch, ổn định và dễ query.

Cấu trúc normalized data đề xuất:

01\_building.json  
02\_floors.json  
03\_rooms.json  
04\_thermal\_zones.json  
05\_surfaces.json  
06\_fenestrations.json  
07\_materials.json  
08\_constructions.json  
09\_hvac\_equipment.json  
10\_electrical\_equipment.json  
11\_structural\_elements.json  
12\_zone\_equipment\_map.json  
13\_schedules.json  
14\_internal\_gains.json  
15\_energyplus\_mapping.json  
16\_semantic\_graph.json  
17\_missing\_metadata\_report.json  
18\_xeokit\_asset\_map.json  
19\_realtime\_variable\_schema.json  
20\_mapping\_quality\_report.json  
21\_viewer\_manifest.json  
22\_layer\_object\_index.json  
23\_floor\_object\_index.json

Ý nghĩa:

01\_building.json  
→ thông tin building tổng thể

02\_floors.json  
→ danh sách tầng, cao độ, alias giữa ARCH/HVAC/ELE/STRUCT

03\_rooms.json  
→ IfcSpace/room từ ARCH As-Built

04\_thermal\_zones.json  
→ zone dùng cho EnergyPlus và dashboard

05\_surfaces.json  
→ wall/floor/roof/ceiling surfaces

06\_fenestrations.json  
→ window/door/opening

07\_materials.json  
→ material từ ARCH/STRUCT

08\_constructions.json  
→ construction layer phục vụ EnergyPlus

09\_hvac\_equipment.json  
→ HVAC device, duct, pipe, valve, fan, pump, terminal

10\_electrical\_equipment.json  
→ light, outlet, board, cable tray

11\_structural\_elements.json  
→ slab, beam, column, wall, material, mass

12\_zone\_equipment\_map.json  
→ mapping giữa zone và thiết bị HVAC/ELE

13\_schedules.json  
→ occupancy, lighting, equipment, HVAC schedule

14\_internal\_gains.json  
→ people, lighting, plug load approximation

15\_energyplus\_mapping.json  
→ mapping GreenFlow entity sang EnergyPlus object

16\_semantic\_graph.json  
→ node/edge cho graph database

17\_missing\_metadata\_report.json  
→ report thiếu metadata

18\_xeokit\_asset\_map.json  
→ mapping giữa entity\_id và xeokit object/model/asset

19\_realtime\_variable\_schema.json  
→ schema biến realtime/simulation gắn vào object

20\_mapping\_quality\_report.json  
→ kiểm tra chất lượng spatial join và mapping

21\_viewer\_manifest.json  
→ manifest để frontend load XKT layer

22\_layer\_object\_index.json  
→ index object theo layer

23\_floor\_object\_index.json  
→ index object theo floor

---

## **11\. Logic tạo Thermal Zone**

Không phải mỗi IfcSpace đều nên trở thành một EnergyPlus Zone riêng. Nếu làm vậy model sẽ nặng, khó kiểm soát và khó calibrate.

Nên gom room thành thermal zone theo logic:

same floor  
\+ same room type  
\+ same orientation  
\+ same usage schedule  
\+ same HVAC served area  
\+ similar envelope condition

Ví dụ thermal zone:

Level\_01\_OpenOffice\_East  
Level\_01\_OpenOffice\_West  
Level\_02\_MeetingRooms  
Level\_03\_Corridor  
Level\_04\_OfficeWest  
Basement\_Parking  
Roof\_TechnicalArea

Mỗi room vẫn giữ trong graph, nhưng EnergyPlus có thể dùng zone đã gom.

Mapping graph:

Room → PART\_OF\_ZONE → ThermalZone  
ThermalZone → HAS\_SURFACE → Surface  
ThermalZone → HAS\_SCHEDULE → Schedule  
ThermalZone → HAS\_HVAC\_TARGET → HVACEquipment  
ThermalZone → HAS\_LIGHTING → LightFixtureGroup  
ThermalZone → HAS\_ELECTRIC\_EQUIPMENT → OutletGroup

Mapping viewer:

Room object → spaces.xkt  
ThermalZone object → thermal\_zones.xkt  
ThermalZone state → colorize thermal\_zones object

---

## **12\. Mapping HVAC/ELE vào ARCH As-Built**

HVAC và ELE thường không có IfcSpace đầy đủ, nên không thể biết trực tiếp thiết bị thuộc phòng nào. Cách đúng là spatial join dựa trên ARCH As-Built.

### **12.1. Chuẩn hóa tầng**

Tạo bảng alias tầng:

{  
  "00\_Kellari": "Basement",  
  "01\_Kerros": "Level\_01",  
  "02\_Kerros": "Level\_02",  
  "03\_Kerros": "Level\_03",  
  "04\_Kerros": "Level\_04",  
  "05\_Kerros": "Level\_05",  
  "Vesikatto": "Roof"  
}

Tất cả tọa độ cần thống nhất đơn vị:

x\_m \= x\_ifc\_mm / 1000  
y\_m \= y\_ifc\_mm / 1000  
z\_m \= z\_ifc\_mm / 1000

Mục tiêu:

ARCH floor  
HVAC floor  
ELE floor  
STRUCT floor  
→ cùng floor\_id chuẩn của GreenFlow

---

### **12.2. Spatial Join cho thiết bị dạng điểm**

Áp dụng cho:

IfcLightFixture  
IfcOutlet  
IfcAirTerminal  
IfcCooledBeam  
IfcFan  
IfcPump  
IfcValve  
IfcElectricDistributionBoard

Logic:

1\. Lấy centroid hoặc placement point của thiết bị.  
2\. Xác định tầng bằng z-coordinate hoặc IfcBuildingStorey.  
3\. Lấy danh sách IfcSpace trên tầng tương ứng.  
4\. Kiểm tra point nằm trong footprint/volume của space nào.  
5\. Nếu nằm trong space → assign room\_id và zone\_id.  
6\. Nếu không nằm trong space → nearest room/zone theo khoảng cách.  
7\. Ghi mapping\_method và confidence score.

Output:

{  
  "equipment\_id": "airterminal\_00451",  
  "equipment\_type": "AirTerminal",  
  "ifc\_global\_id": "3Df9Axxxx",  
  "xeokit\_object\_id": "hvac\_airterminal\_00451",  
  "floor\_id": "level\_03",  
  "room\_id": "room\_03\_215",  
  "zone\_id": "zone\_level03\_openoffice\_east",  
  "mapping\_method": "point\_inside\_space",  
  "confidence": 0.96  
}

---

### **12.3. Spatial Join cho object dạng tuyến**

Áp dụng cho:

IfcDuctSegment  
IfcPipeSegment  
IfcCableCarrierSegment

Không nên gán một duct/pipe/cable tray dài vào một phòng duy nhất, vì các object này có thể đi qua nhiều room hoặc zone.

Logic:

1\. Lấy centerline hoặc bounding box của segment.  
2\. Intersect với nhiều room/zone trên cùng tầng.  
3\. Tính chiều dài hoặc tỷ lệ segment nằm trong từng zone.  
4\. Gán quan hệ segment → PASSES\_THROUGH → zone.  
5\. Nếu segment nối tới terminal/equipment thì suy ra connectivity.  
6\. Lưu confidence score.

Output:

{  
  "segment\_id": "duct\_01231",  
  "xeokit\_object\_id": "hvac\_duct\_01231",  
  "relation": "PASSES\_THROUGH",  
  "zones": \[  
    {  
      "zone\_id": "zone\_level03\_corridor",  
      "length\_ratio": 0.62  
    },  
    {  
      "zone\_id": "zone\_level03\_openoffice\_east",  
      "length\_ratio": 0.38  
    }  
  \],  
  "mapping\_method": "segment\_zone\_intersection",  
  "confidence": 0.89  
}

---

## **13\. Biến động gắn vào object nào?**

### **13.1. Room / ThermalZone**

Đây là object chính cho dashboard vận hành.

Các biến chính:

temperature  
humidity  
occupancy  
cooling\_load\_kw  
heating\_load\_kw  
lighting\_load\_kw  
plug\_load\_kw  
total\_energy\_kwh  
comfort\_risk  
peak\_risk  
anomaly\_score  
co2\_ppm nếu có

Ví dụ state:

{  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "xeokit\_object\_id": "zone\_level03\_openoffice\_east",  
  "timestamp": "2026-06-11T13:05:00+07:00",  
  "temperature": 27.8,  
  "humidity": 62,  
  "occupancy": 18,  
  "cooling\_load\_kw": 12.4,  
  "lighting\_load\_kw": 2.1,  
  "plug\_load\_kw": 3.8,  
  "comfort\_risk": 0.81,  
  "peak\_risk": 0.74,  
  "anomaly\_score": 0.67  
}

Hiển thị trong xeokit:

temperature cao → colorize zone đỏ/cam  
comfort\_risk cao → colorize đỏ/cam \+ warning marker  
occupancy cao → tăng opacity hoặc hiển thị density marker  
peak\_risk cao → highlight object  
anomaly → highlight \+ icon cảnh báo

---

### **13.2. HVAC Equipment**

Các biến chính:

AirTerminal  
→ airflow, supply\_air\_temperature, damper\_position, status

CooledBeam  
→ cooling\_state, valve\_position, cooling\_output

Fan  
→ on/off, speed, power, fault

Pump  
→ on/off, speed, power, fault

Valve  
→ open\_percentage, fault\_state

Duct/Pipe  
→ flow\_direction, estimated\_flow\_rate, temperature

Chiller  
→ cooling\_power, COP, status

Hiển thị trong xeokit:

airflow cao → highlight duct/terminal  
valve open cao → colorize valve xanh  
fan/pump fault → colorize đỏ \+ warning marker  
cooling supply active → highlight pipe/terminal  
device off → opacity thấp

---

### **13.3. Electrical Equipment**

Các biến chính:

LightFixture  
→ on/off, dimming, power\_w

Outlet  
→ plug\_load\_w, estimated\_usage

ElectricalBoard  
→ total\_load\_kw, peak\_warning, fault

CableTray  
→ visualization only

Hiển thị trong xeokit:

đèn bật → colorize/highlight light fixture  
đèn tắt → opacity thấp  
board quá tải → warning marker  
plug load cao → outlet colorize đỏ/cam

---

## **14\. Logic View Mode trên Dashboard**

Dashboard nên có các mode chính.

### **14.1. Architecture View**

Hiển thị:

building shell  
floor  
room  
envelope  
wall  
window  
door  
slab  
roof

Dùng để:

inspect room  
xem diện tích/thể tích  
xem wall/window/slab  
xem material/envelope  
xem cấu trúc không gian cơ bản

Visual:

architecture visible  
spaces optional  
hvac hidden  
electrical hidden  
thermal\_zones low opacity

---

### **14.2. HVAC View**

Hiển thị:

duct  
pipe  
air terminal  
valve  
fan  
pump  
coil  
cooled beam

Dùng để:

xem thiết bị HVAC theo tầng  
xem thiết bị nào gần zone nào  
xem thiết bị nào phục vụ zone nào  
xem action target  
xem trạng thái on/off/fault

Visual:

architecture x-ray hoặc opacity thấp  
hvac visible  
thermal\_zones optional  
electrical hidden

---

### **14.3. Electrical View**

Hiển thị:

light fixture  
outlet  
electrical board  
cable tray  
cable fitting

Dùng để:

xem lighting layout  
xem plug load  
xem board/load warning  
xem đèn bật/tắt/dimming

Visual:

architecture opacity thấp  
electrical visible  
hvac hidden  
thermal\_zones optional

---

### **14.4. Energy View**

Hiển thị zone theo:

cooling\_load\_kw  
heating\_load\_kw  
lighting\_load\_kw  
plug\_load\_kw  
total\_energy\_kwh

Màu đề xuất:

xanh → thấp  
vàng → trung bình  
đỏ → cao

Object chính:

thermal\_zones.xkt

---

### **14.5. Comfort View**

Hiển thị comfort risk.

Rule:

comfort\_risk \< 0.4  
→ bình thường

0.4 ≤ comfort\_risk \< 0.7  
→ cần theo dõi

comfort\_risk ≥ 0.7  
→ rủi ro cao

Visual:

zone bình thường → opacity thấp, màu nhẹ  
zone cần theo dõi → màu vàng/cam  
zone rủi ro cao → màu đỏ/cam \+ highlight \+ warning marker

---

### **14.6. Occupancy View**

Hiển thị mật độ người theo zone.

Visual:

occupancy thấp → zone mờ  
occupancy trung bình → zone rõ hơn  
occupancy cao → zone đậm \+ density marker

Dùng để:

giải thích energy load  
giải thích comfort risk  
hỗ trợ action tối ưu HVAC/lighting

---

### **14.7. Action / Anomaly View**

Hiển thị cảnh báo và đề xuất hành động.

Ví dụ:

Zone Level\_03\_OpenOffice\_East comfort risk cao  
→ kiểm tra AirTerminal AT-00451  
→ kiểm tra airflow  
→ giảm cooling setpoint hoặc tăng airflow  
→ tắt bớt lighting nếu occupancy thấp

Visual:

target zone → highlight  
related HVAC device → highlight  
related electrical device → highlight  
unrelated objects → opacity thấp

---

## **15\. Database Architecture đề xuất**

Không nên dùng một loại database duy nhất cho tất cả. GreenFlow nên dùng kiến trúc hybrid.

### **15.1. MVP khuyến nghị**

PostgreSQL  
\+ PostGIS  
\+ TimescaleDB  
\+ pgvector  
\+ Object Storage

Vai trò:

PostgreSQL  
→ building entities, metadata, users, projects, simulation cases

PostGIS  
→ footprint, polygon, bbox, spatial join, geometry reference

TimescaleDB  
→ time-series data: temperature, energy, occupancy, state

pgvector  
→ embeddings cho RAG/document retrieval

Object Storage  
→ IFC, XKT, metadata JSON, EnergyPlus CSV/SQLite output

---

### **15.2. GraphDB**

Có thể dùng 2 hướng.

#### **Hướng A — Postgres-first Graph**

Lưu node/edge ngay trong PostgreSQL:

entities table  
relations table

Phù hợp cho MVP vì dễ deploy, đơn giản và ít overhead.

#### **Hướng B — Neo4j / Memgraph**

Dùng khi muốn GraphRAG mạnh hơn:

Postgres \= source of truth  
Neo4j/Memgraph \= semantic building graph  
TimescaleDB \= dynamic state  
Object Storage \= IFC/XKT/simulation assets  
pgvector \= document/vector retrieval

Phù hợp khi cần hỏi multi-hop:

Zone này do thiết bị HVAC nào phục vụ?  
Đèn nào nằm trong zone có comfort risk cao?  
Tầng nào có peak demand cao nhất và liên quan tới board nào?  
Valve nào có thể tác động tới zone đang nóng?  
Tại sao phòng này nóng: do occupancy, solar gain hay HVAC?

---

## **16\. Graph Schema đề xuất**

### **16.1. Node chính**

Building  
Floor  
Room  
ThermalZone  
Surface  
Window  
Door  
Material  
Construction  
HVACSystem  
HVACEquipment  
AirTerminal  
Duct  
Pipe  
Valve  
Pump  
Fan  
Coil  
ElectricalSystem  
LightFixture  
Outlet  
ElectricalBoard  
CableTray  
StructuralElement  
Sensor  
Meter  
Schedule  
SimulationCase  
EnergyPlusOutput  
Action  
Anomaly  
ViewerAsset  
XeokitObject

### **16.2. Relationship chính**

(Building)-\[:HAS\_FLOOR\]-\>(Floor)  
(Floor)-\[:HAS\_ROOM\]-\>(Room)  
(Room)-\[:PART\_OF\_ZONE\]-\>(ThermalZone)  
(ThermalZone)-\[:HAS\_SURFACE\]-\>(Surface)  
(Surface)-\[:HAS\_OPENING\]-\>(Window)  
(Surface)-\[:USES\_CONSTRUCTION\]-\>(Construction)  
(Construction)-\[:HAS\_MATERIAL\]-\>(Material)

(HVACEquipment)-\[:LOCATED\_ON\]-\>(Floor)  
(HVACEquipment)-\[:SERVES\_OR\_NEAR\]-\>(ThermalZone)  
(AirTerminal)-\[:SUPPLIES\_AIR\_TO\]-\>(ThermalZone)  
(Duct)-\[:CONNECTED\_TO\]-\>(HVACEquipment)  
(Pipe)-\[:CONNECTED\_TO\]-\>(HVACEquipment)

(LightFixture)-\[:LOCATED\_IN\]-\>(ThermalZone)  
(Outlet)-\[:LOCATED\_IN\]-\>(ThermalZone)  
(ElectricalBoard)-\[:FEEDS\]-\>(LightFixture)

(StructuralElement)-\[:HAS\_MATERIAL\]-\>(Material)  
(StructuralElement)-\[:BELONGS\_TO\]-\>(Floor)

(ThermalZone)-\[:HAS\_SCHEDULE\]-\>(Schedule)  
(SimulationCase)-\[:USES\_ZONE\]-\>(ThermalZone)  
(SimulationCase)-\[:GENERATES\]-\>(EnergyPlusOutput)

(Action)-\[:TARGETS\]-\>(ThermalZone)  
(Action)-\[:TARGETS\_DEVICE\]-\>(HVACEquipment)  
(Anomaly)-\[:DETECTED\_IN\]-\>(ThermalZone)

(XeokitObject)-\[:REPRESENTS\]-\>(ThermalZone)  
(XeokitObject)-\[:REPRESENTS\]-\>(HVACEquipment)  
(XeokitObject)-\[:BELONGS\_TO\_ASSET\]-\>(ViewerAsset)

---

## **17\. EnergyPlus Mapping**

EnergyPlus không cần toàn bộ BIM. Nó chỉ cần phần dữ liệu phục vụ mô phỏng nhiệt và năng lượng.

### **17.1. ARCH → EnergyPlus**

IfcBuilding  
→ Building

IfcSpace  
→ Zone hoặc thermal zone source

IfcRelSpaceBoundary  
→ surface adjacency

IfcWall  
→ BuildingSurface:Detailed

IfcSlab  
→ Floor / RoofCeiling:Detailed

IfcWindow  
→ FenestrationSurface:Detailed

IfcDoor  
→ Door / FenestrationSurface:Detailed

IfcMaterial  
→ Material

IfcMaterialLayerSet  
→ Construction

### **17.2. HVAC → EnergyPlus MVP**

Phase 1 không build full HVAC network.

Dùng:

ThermalZone  
→ ZoneHVAC:IdealLoadsAirSystem  
→ ThermostatSetpoint:DualSetpoint  
→ DesignSpecification:OutdoorAir

HVAC IFC dùng cho:

AirTerminal → map zone served  
Duct/Pipe → graph \+ visualization  
Valve → control/action target  
Fan/Pump/Coil → graph, phase 2

### **17.3. ELE → EnergyPlus**

IfcLightFixture  
→ Lights

IfcOutlet  
→ ElectricEquipment

IfcElectricDistributionBoard  
→ graph/meter metadata

IfcCableCarrierSegment  
→ 3D view only

### **17.4. STRUCTURAL → EnergyPlus**

IfcSlab / IfcWall / IfcRoof  
→ material/construction/thermal mass reference

IfcColumn / IfcBeam  
→ InternalMass approximation hoặc bỏ qua

IfcMaterial / Quantity  
→ material library, LCA, thermal mass

---

## **18\. Luồng dữ liệu từ EnergyPlus sang xeokit Dashboard**

EnergyPlus chạy offline hoặc batch để tạo baseline.

Output cần lấy:

Zone Mean Air Temperature  
Zone Air Relative Humidity  
Zone Ideal Loads Supply Air Total Cooling Energy  
Zone Ideal Loads Supply Air Total Heating Energy  
Zone Lights Electricity Energy  
Zone Electric Equipment Electricity Energy  
Electricity:Facility  
Facility Total Electricity Demand Rate

Sau khi chạy EnergyPlus:

EnergyPlus output SQLite/CSV  
→ parse  
→ map output variable về zone\_id  
→ lưu TimescaleDB  
→ cập nhật entity\_state\_latest  
→ frontend nhận WebSocket/API  
→ xeokit đổi màu/opacity/highlight thermal zone object

Ví dụ state:

{  
  "zone\_id": "zone\_level03\_openoffice\_east",  
  "xeokit\_object\_id": "zone\_level03\_openoffice\_east",  
  "metric": "cooling\_load\_kw",  
  "value": 12.4,  
  "source": "energyplus\_baseline",  
  "timestamp": "2026-06-11T13:00:00+07:00"  
}

Ví dụ WebSocket payload:

{  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "xeokit\_object\_id": "zone\_level03\_openoffice\_east",  
  "state": {  
    "temperature": 27.8,  
    "comfort\_risk": 0.81,  
    "cooling\_load\_kw": 12.4  
  },  
  "style": {  
    "color": "\#ff4d4f",  
    "opacity": 0.55,  
    "highlight": true,  
    "label": "Comfort Risk 81%"  
  }  
}

---

## **19\. API tối thiểu cần có**

### **19.1. Building / Floor / Zone API**

GET /api/buildings/{building\_id}  
GET /api/floors/{floor\_id}  
GET /api/rooms/{room\_id}  
GET /api/zones/{zone\_id}

### **19.2. Entity API**

GET /api/entities/{entity\_id}  
GET /api/entities/{entity\_id}/state  
GET /api/entities/{entity\_id}/history  
GET /api/entities/{entity\_id}/neighbors  
GET /api/entities/{entity\_id}/related-objects

### **19.3. xeokit Viewer API**

GET /api/3d/viewer-manifest?building\_id=...  
GET /api/3d/assets?building\_id=...  
GET /api/3d/xeokit-object-map?building\_id=...  
GET /api/3d/layer-object-index?building\_id=...  
GET /api/3d/floor-object-index?building\_id=...

### **19.4. View Mode API**

GET /api/view/energy?floor\_id=...  
GET /api/view/comfort?floor\_id=...  
GET /api/view/occupancy?floor\_id=...  
GET /api/view/hvac?floor\_id=...  
GET /api/view/electrical?floor\_id=...  
GET /api/view/action?floor\_id=...

### **19.5. Agent / Simulation API**

POST /api/agent/query  
POST /api/simulation/run  
GET /api/simulation/{case\_id}/status  
GET /api/simulation/{case\_id}/outputs

### **19.6. WebSocket**

/ws/building/{building\_id}/state  
/ws/building/{building\_id}/alerts  
/ws/building/{building\_id}/actions

---

## **20\. Object Inspector trên Dashboard**

Khi user click object trong xeokit, GreenFlow mở Object Inspector.

### **20.1. Với ThermalZone**

Hiển thị:

Zone name  
Floor  
Room list  
Area  
Volume  
Temperature  
Humidity  
Occupancy  
Cooling load  
Lighting load  
Plug load  
Comfort risk  
Peak risk  
Anomaly score  
Serving HVAC devices  
Lighting fixtures  
EnergyPlus baseline comparison  
Suggested actions

### **20.2. Với HVAC Equipment**

Hiển thị:

Device name  
Device type  
IFC type  
Floor  
Assigned room  
Assigned zone  
Status  
Airflow / valve position / fan speed  
Power  
Fault state  
Connected duct/pipe  
Zones served  
Available actions

### **20.3. Với Electrical Equipment**

Hiển thị:

Device name  
Device type  
Floor  
Room/zone  
Power  
On/off  
Dimming  
Board connection  
Peak warning  
Related zone energy impact

### **20.4. Với Architecture Object**

Hiển thị:

Object name  
IFC type  
Material  
Construction  
Area  
Boundary relation  
Related zone  
EnergyPlus surface mapping

---

## **21\. GraphRAG Agent**

GraphRAG dùng semantic graph \+ realtime state \+ EnergyPlus output để trả lời câu hỏi có giải thích.

Luồng:

User question  
→ detect entity / intent  
→ nếu user đang click object thì lấy selected\_entity\_id  
→ query GraphDB lấy quan hệ building  
→ query TimescaleDB lấy state mới nhất  
→ query EnergyPlus baseline  
→ query document/vector nếu cần  
→ LLM sinh câu trả lời có giải thích  
→ frontend highlight các object liên quan trong xeokit

Ví dụ câu hỏi:

“Tại sao zone này đang nóng?”

Agent cần lấy:

ThermalZone  
→ current temperature  
→ occupancy  
→ cooling load  
→ windows/orientation  
→ air terminals serving zone  
→ HVAC state  
→ lighting/plug load  
→ baseline EnergyPlus

Trả lời mong muốn:

Zone này nóng chủ yếu do cooling load đang cao hơn baseline, occupancy cao và lighting load vẫn bật mạnh. HVAC terminal phục vụ zone là AT-00451 và AT-00452, hiện airflow thấp hơn mức giả lập. Không có dấu hiệu peak do plug load.

Action đi kèm trên viewer:

highlight zone đang nóng  
highlight air terminal liên quan  
highlight light fixtures liên quan  
dim các object không liên quan

---

## **22\. Validation bắt buộc**

Để hệ thống đáng tin, cần có report kiểm tra sau khi parse, convert và mapping.

Checklist:

1\. Bao nhiêu ARCH rooms được tạo?  
2\. Bao nhiêu thermal zones được tạo?  
3\. Bao nhiêu wall/window/slab được map vào surfaces?  
4\. Bao nhiêu HVAC equipment map được vào zone?  
5\. Bao nhiêu light fixture map được vào zone?  
6\. Bao nhiêu outlet map được vào zone?  
7\. Bao nhiêu object không map được?  
8\. Object nào lệch tầng?  
9\. Object nào thiếu geometry?  
10\. Object nào thiếu material/schedule/power?  
11\. Bao nhiêu xeokit\_object\_id map được về entity\_id?  
12\. Bao nhiêu entity không có object 3D?  
13\. Bao nhiêu object 3D không có metadata?  
14\. Bao nhiêu object 3D không có ifc\_global\_id?  
15\. Bao nhiêu XKT asset load thành công?

File report:

17\_missing\_metadata\_report.json  
20\_mapping\_quality\_report.json  
24\_xeokit\_conversion\_report.json  
25\_viewer\_asset\_validation\_report.json

Ví dụ quality score:

{  
  "room\_count": 248,  
  "thermal\_zone\_count": 42,  
  "hvac\_airterminal\_zone\_mapping\_rate": 0.93,  
  "light\_fixture\_zone\_mapping\_rate": 0.97,  
  "outlet\_zone\_mapping\_rate": 0.88,  
  "xeokit\_object\_entity\_mapping\_rate": 0.98,  
  "objects\_without\_metadata": 27,  
  "unmapped\_objects": 421,  
  "warnings": \[  
    "Some roof HVAC elements could not be matched to ARCH roof level",  
    "Some cable trays pass through multiple zones",  
    "Some objects have geometry but missing source IFC GlobalId"  
  \]  
}

---

## **23\. MVP triển khai theo thứ tự**

### **Phase 1 — Static xeokit BIM Viewer**

Mục tiêu:

Convert IFC → XKT  
Load XKT bằng xeokit  
Tách layer Architecture / Spaces / HVAC / Electrical / Structural / Terrain  
Click object để xem metadata

Output:

viewer-manifest.json  
xkt assets  
xeokit\_object\_map.json  
basic Object Inspector  
layer checkbox UI

---

### **Phase 2 — Semantic Building Graph**

Mục tiêu:

Parse IFC metadata  
Sinh normalized JSON  
Tạo entities \+ relations  
Map Room → ThermalZone  
Map HVAC/ELE → Zone bằng spatial join  
Map xeokit object → entity

Output:

entities table  
relations table  
semantic\_graph.json  
zone\_equipment\_map.json  
xeokit\_asset\_map.json  
mapping quality report

---

### **Phase 3 — EnergyPlus Baseline**

Mục tiêu:

ARCH geometry  
\+ material defaults  
\+ occupancy schedule defaults  
\+ lighting load từ ELE  
\+ equipment load từ outlet approximation  
\+ IdealLoads HVAC  
→ chạy EnergyPlus  
→ lưu output vào TimescaleDB

Output:

EnergyPlus IDF  
EnergyPlus output CSV/SQLite  
energyplus\_mapping.json  
zone baseline time-series

---

### **Phase 4 — Dynamic xeokit Dashboard**

Mục tiêu:

Map EnergyPlus output → zone\_id  
Update zone state  
Render heatmap energy/comfort/occupancy trong xeokit  
Nhận WebSocket realtime state  
Đổi màu/opacity/highlight object

Output:

Energy View  
Comfort View  
Occupancy View  
Action / Anomaly View  
WebSocket state update

---

### **Phase 5 — GraphRAG Agent**

Mục tiêu:

User hỏi theo object, zone, floor hoặc hệ thống  
→ query GraphDB  
→ query latest state  
→ query simulation output  
→ trả lời có giải thích  
→ highlight object liên quan trong xeokit viewer

Output:

chatbot agent  
explainable query  
object-linked answer  
viewer highlight action

---

## **24\. Cấu trúc frontend đề xuất**

src/  
  app/  
    dashboard/  
      page.tsx

  components/  
    viewer/  
      GreenFlowXeokitViewer.tsx  
      LayerPanel.tsx  
      ViewModeToolbar.tsx  
      ObjectInspector.tsx  
      FloorSelector.tsx  
      MetricLegend.tsx  
      AlertOverlay.tsx

  services/  
    viewerManifestService.ts  
    entityService.ts  
    stateWebSocket.ts  
    graphService.ts  
    simulationService.ts

  stores/  
    viewerStore.ts  
    selectedEntityStore.ts  
    layerStore.ts  
    stateStore.ts

  types/  
    building.ts  
    entity.ts  
    viewer.ts  
    energy.ts  
    graph.ts

Viewer responsibilities:

GreenFlowXeokitViewer  
→ init xeokit viewer  
→ load XKT assets  
→ register object maps  
→ handle picking  
→ update object visual state  
→ respond to view mode changes

LayerPanel responsibilities:

toggle architecture  
toggle spaces  
toggle thermal zones  
toggle HVAC  
toggle electrical  
toggle structural  
toggle terrain

ObjectInspector responsibilities:

show metadata  
show latest state  
show graph neighbors  
show related devices  
show suggested actions

---

## **25\. Cấu trúc backend đề xuất**

backend/  
  app/  
    api/  
      buildings.py  
      floors.py  
      rooms.py  
      zones.py  
      entities.py  
      viewer\_assets.py  
      states.py  
      simulation.py  
      agent.py

    services/  
      ifc\_parser\_service.py  
      xkt\_conversion\_service.py  
      spatial\_join\_service.py  
      energyplus\_service.py  
      graph\_service.py  
      state\_service.py  
      viewer\_manifest\_service.py

    models/  
      building.py  
      entity.py  
      relation.py  
      state.py  
      simulation.py  
      viewer\_asset.py

    workers/  
      parse\_ifc\_worker.py  
      convert\_xkt\_worker.py  
      run\_energyplus\_worker.py  
      build\_graph\_worker.py

Backend responsibilities:

IFC parsing  
XKT conversion orchestration  
normalized JSON generation  
spatial join  
EnergyPlus model generation  
time-series ingestion  
GraphDB sync  
viewer manifest generation  
WebSocket state broadcasting

---

## **26\. Bảng database tối thiểu**

### **26.1. entities**

id  
entity\_id  
entity\_type  
name  
ifc\_global\_id  
ifc\_class  
floor\_id  
room\_id  
zone\_id  
source\_file  
properties\_json  
created\_at  
updated\_at

### **26.2. relations**

id  
source\_entity\_id  
relation\_type  
target\_entity\_id  
properties\_json  
confidence  
created\_at  
updated\_at

### **26.3. viewer\_assets**

id  
asset\_id  
building\_id  
layer  
model\_id  
format  
asset\_url  
metadata\_url  
default\_visible  
created\_at  
updated\_at

### **26.4. xeokit\_object\_map**

id  
building\_id  
asset\_id  
model\_id  
xeokit\_object\_id  
ifc\_global\_id  
entity\_id  
entity\_type  
floor\_id  
room\_id  
zone\_id  
layer  
properties\_json  
created\_at  
updated\_at

### **26.5. entity\_state\_latest**

entity\_id  
timestamp  
state\_json  
source  
updated\_at

### **26.6. entity\_state\_timeseries**

entity\_id  
timestamp  
metric  
value  
unit  
source

---

## **27\. Quy tắc visual style trong xeokit**

### **27.1. Layer visibility**

Architecture View:  
architecture visible  
thermal zones optional  
hvac hidden  
electrical hidden

HVAC View:  
architecture low opacity  
hvac visible  
electrical hidden  
thermal zones optional

Electrical View:  
architecture low opacity  
electrical visible  
hvac hidden  
thermal zones optional

Energy View:  
architecture low opacity  
thermal zones visible  
hvac/electrical hidden by default

Action View:  
target zone highlighted  
related devices highlighted  
unrelated objects faded

### **27.2. Metric color**

Energy / Load:  
low → green  
medium → yellow/orange  
high → red

Comfort Risk:  
normal → green/neutral  
watch → orange  
high risk → red

Occupancy:  
low → low opacity  
medium → medium opacity  
high → high opacity \+ density marker

Anomaly:  
normal → no highlight  
anomaly → red highlight \+ warning marker

### **27.3. Object interaction**

hover → subtle highlight  
click → select object  
double click → focus camera on object  
right panel → show Object Inspector  
related object → secondary highlight  
unrelated object → fade

---

## **28\. Điểm quan trọng cần tránh**

### **28.1. Không dùng IFC trực tiếp làm realtime dashboard**

IFC là source data, không phải runtime asset cho state update. Frontend nên load XKT đã tối ưu.

### **28.2. Không để object ID random**

Nếu object ID thay đổi sau mỗi lần convert, toàn bộ mapping sẽ hỏng. Cần giữ stable ID theo `entity_id` hoặc `ifc_global_id`.

### **28.3. Không gộp mọi layer vào một asset duy nhất**

Nếu gộp hết vào một file, việc bật/tắt layer, load theo floor và optimize sẽ khó hơn. Nên tách theo discipline và mục đích hiển thị.

### **28.4. Không đưa toàn bộ BIM vào EnergyPlus**

EnergyPlus chỉ cần geometry nhiệt, material, schedules, internal gains và HVAC abstraction phù hợp. Duct, cable tray, beam, column chi tiết chủ yếu dùng cho visualization và graph.

### **28.5. Không dùng HVAC/ELE làm nguồn zoning**

ARCH As-Built phải là source of truth cho room, space, zone và envelope. HVAC/ELE chỉ overlay và spatial join vào zone.

---

## **29\. Kết luận kiến trúc**

GreenFlow nên được thiết kế theo hướng:

ARCH As-Built  
\= source of truth cho building geometry, room, zone, envelope

HVAC Permit  
\= source cho HVAC equipment, duct, pipe, terminal, control/action target

ELE Permit  
\= source cho lighting, outlet, board, cable tray, electrical view

STRUCTURAL Permit  
\= source cho material, mass, LCA, structural view

Terrain  
\= source cho site/context/shading visualization

Stack chính:

xeokit SDK  
\+ XKT geometry assets  
\+ xeokit object/entity mapping  
\+ PostgreSQL/PostGIS  
\+ TimescaleDB  
\+ pgvector  
\+ Object Storage  
\+ Neo4j/Memgraph nếu cần GraphRAG nâng cao  
\+ EnergyPlus baseline simulation

3D dashboard hoạt động theo logic:

Static BIM geometry bằng XKT  
\+ stable xeokit\_object\_id  
\+ entity mapping  
\+ dynamic state overlay  
\+ graph relationships  
\+ EnergyPlus simulation output  
\+ GraphRAG explanation

Cách đúng:

IFC  
→ normalized data  
→ semantic graph  
→ XKT assets  
→ xeokit Viewer  
→ EnergyPlus model  
→ simulation/time-series  
→ dynamic 3D dashboard  
→ GraphRAG agent

Với cấu trúc này, GreenFlow có thể vừa hiển thị tòa nhà 3D chi tiết, vừa thay đổi theo biến năng lượng/vận hành, vừa giải thích được vì sao một zone nóng, tiêu thụ cao, rủi ro comfort cao hoặc cần hành động điều khiển.

Điểm cốt lõi của GreenFlow là:

xeokit không chỉ để xem BIM.  
xeokit là lớp giao diện 3D semantic để nối geometry, entity, state, EnergyPlus và GraphDB thành một digital twin có thể vận hành được.

