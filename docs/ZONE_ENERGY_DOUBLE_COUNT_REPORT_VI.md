# Bao Cao Ngan: Rui Ro Tinh Trung Nang Luong Giua Zone Lon Va Zone Nho

## 1. Tom tat van de

Team dang phat hien mot rui ro trong du lieu nang luong hien thi tren dashboard.

Hien tai he thong co ca:

- **Zone nho**: cac phong hoac khu vuc that trong toa nha.
- **Zone lon / aggregate zone**: cac vung tong hop nhu `VOLUME / OFFICE`, `GFA`, `GFA 250mm`, `HEATED NETAREA`.

Van de la mot so zone lon nay co ve dang bao trum nhieu zone nho ben trong, nhung pipeline hien tai lai xem chung nhu zone binh thuong va van gan load dien rieng cho chung.

Noi cach don gian:

> Mot phan dien co the dang bi tinh hai lan: mot lan o zone lon, va mot lan nua o cac zone nho nam ben trong zone lon do.

## 2. Vi du cu the

Zone:

```text
VOLUME / OFFICE:VOLUME / OFFICE:2646424
```

Tuong ung voi:

```text
zone_id: tz_2yC6uZ1Mj3WfWcT4GmORMG
EnergyPlus zone: ZN_0265_925E8FE2
```

Zone nay co dien tich rat lon, khoang `3712 m2`, va co thoi diem load khoang `100.2 kW`.

Khi kiem tra hinh hoc, zone nay co kha nang bao phu rat nhieu space/zone nho khac. Neu dashboard cong load cua zone nay, roi lai cong tiep load cua cac zone nho ben trong, tong dien nang se bi cao hon thuc te.

## 3. Anh huong

Rui ro nay co the anh huong den:

- Tong dien nang hien thi tren dashboard.
- Load cua cac electrical board.
- Bang xep hang zone tieu thu dien nhieu nhat.
- Heatmap nang luong trong 3D view.
- Cac KPI, canh bao peak demand, va ket qua agent phan tich.

Kiem tra nhanh local cho thay nhom zone nghi la aggregate/gross zone chiem ty le rat lon trong tong kWh. Vi vay day khong chi la loi hien thi nho, ma co the lam sai lech so lieu tong hop.

## 4. Thong ke audit so bo

Nguon thong ke: parquet `final_zone_device_power_timeseries.parquet`.

Rule phan loai audit ban dau:

- `aggregate_context`: zone co ten/kieu aggregate ro rang nhu `VOLUME /`, `GFA`, `GFA 250mm`, `HEATED NETAREA`, `NETAREA`, `GROSS`. Nhom nay duoc xem la ngu canh tong hop va co the loai khoi phep cong nang luong khi bat che do dedup.
- `review_required`: zone co tin hieu can review nhu `Turning Free Space`, `SHAFT`, `CHASE`, `VENT`, dien tich rat lon, hoac chieu cao suy ra bat thuong. Nhom nay **chua tu dong bi loai**, vi van co the la thermal zone hop le.
- `atomic_energy_zone`: cac zone con/phong/khu vuc that con lai.

Day la rule de audit nhanh. Production hien tai chi tu dong loai cac ten aggregate ro rang; cac heuristic hinh hoc va context name duoc giu lai de review.

### 4.1 Tong quan

| Nhom zone | So zone | Tong kWh | Ty le kWh | Tai trung binh | Tong peak rieng le | Peak lon nhat 1 zone | Dien tich | Ty le dien tich | kWh/m2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Zone nho / `atomic_energy_zone` | 210 | 124,460.35 | 35.50% | 85.01 kW | 341.17 kW | 31.26 kW | 13,815.36 m2 | 18.04% | 9.01 |
| Zone gop / `aggregate_context` | 98 | 226,136.72 | 64.50% | 154.46 kW | 552.25 kW | 103.43 kW | 62,784.68 m2 | 81.96% | 3.60 |
| Tong raw hien tai | 308 | 350,597.07 | 100.00% | 239.48 kW | 893.42 kW | - | 76,600.04 m2 | 100.00% | 4.58 |

Nhan xet nhanh:

- Zone gop chiem **98/308 zone**, nhung dong gop **64.50% tong kWh**.
- Zone nho chiem **210/308 zone**, dong gop **35.50% tong kWh**.
- Tai thoi diem peak raw `2024-04-29 16:00`, tong load la **893.36 kW**:
  - Zone gop dong gop **552.25 kW**.
  - Zone nho dong gop **341.11 kW**.

### 4.2 Co cau dien nang theo nhom

| Nhom zone | Lights kWh | Lights % | Equipment kWh | Equipment % | HVAC kWh | HVAC % |
|---|---:|---:|---:|---:|---:|---:|
| Zone nho / `atomic_energy_zone` | 28,767.12 | 23.11% | 67,129.72 | 53.94% | 28,563.52 | 22.95% |
| Zone gop / `aggregate_context` | 114,441.03 | 50.61% | 85,055.60 | 37.61% | 26,640.09 | 11.78% |

Nhan xet:

- Zone gop dang gan rat nhieu load lighting.
- Zone nho co ty trong equipment cao hon.
- Neu dashboard cong ca hai nhom, co kha nang lighting va tong load bi doi len dang ke.

### 4.3 Top zone gop dong gop kWh cao nhat

| Zone | Ten / so | Tang | Dien tich | Tong kWh | Peak kW | Ly do bi xep zone gop |
|---|---|---|---:|---:|---:|---|
| `ZN_0265_925E8FE2` | `VOLUME / OFFICE:2646424` | Foundation | 3,712.13 m2 | 39,580.56 | 103.43 | aggregate name, dien tich lon, chieu cao bat thuong |
| `ZN_0071_763C5296` | `VENT 510` | Level_05 | 882.54 m2 | 11,866.64 | 25.41 | context name |
| `ZN_0240_1F18C60A` | `GFA 1` | Level_01 | 3,712.13 m2 | 11,081.79 | 27.05 | aggregate name, dien tich lon |
| `ZN_0241_30D90A96` | `GFA 2` | Level_02 | 3,712.13 m2 | 11,061.73 | 26.94 | aggregate name, dien tich lon |
| `ZN_0242_131CC093` | `GFA 3` | Level_03 | 3,712.13 m2 | 11,035.97 | 26.80 | aggregate name, dien tich lon |

### 4.4 Top zone nho dong gop kWh cao nhat

| Zone | Ten / so | Tang | Dien tich | Tong kWh | Peak kW |
|---|---|---|---:|---:|---:|
| `ZN_0249_66A29656` | `OFFICE TSTO1` | Level_02 | 1,145.48 m2 | 11,854.21 | 31.26 |
| `ZN_0252_046FBA35` | `OFFICE TSTO6` | Level_03 | 876.06 m2 | 9,066.57 | 23.91 |
| `ZN_0256_61C1CDEF` | `OFFICE TSTO10` | Level_04 | 876.06 m2 | 9,065.39 | 23.91 |
| `ZN_0248_B5DAE375` | `OFFICE TSTO2` | Level_02 | 876.06 m2 | 9,064.23 | 23.91 |
| `ZN_0251_D0166AAF` | `OFFICE TSTO5` | Level_03 | 643.70 m2 | 6,661.66 | 17.56 |

### 4.5 Zone gop theo tang

| Tang | So zone gop | Tong kWh | Tong peak rieng le |
|---|---:|---:|---:|
| Foundation | 1 | 39,580.56 | 103.43 kW |
| Level_01 | 17 | 36,126.94 | 87.90 kW |
| Level_02 | 15 | 33,162.90 | 80.68 kW |
| Level_03 | 16 | 33,120.05 | 80.38 kW |
| Level_04 | 16 | 33,019.10 | 79.82 kW |
| Level_05 | 15 | 27,248.91 | 62.57 kW |
| Basement | 18 | 23,878.25 | 57.46 kW |

### 4.6 Breakdown theo ly do bi xep zone gop

Luu y: mot zone co the co nhieu ly do, nen cac dong duoi day co the overlap nhau.

| Ly do | So zone | Tong kWh lien quan |
|---|---:|---:|
| Ten/kieu aggregate: `VOLUME`, `GFA`, `HEATED NETAREA`, `NETAREA`, `GROSS` | 20 | 210,655.47 |
| Dien tich rat lon | 17 | 204,382.74 |
| Chieu cao suy ra bat thuong | 4 | 39,745.15 |
| Context name: `Turning Free Space`, `SHAFT`, `CHASE`, `VENT` | 75 | 15,316.66 |

## 5. Nguyen nhan kha nang cao

Pipeline hien tai dang lay tat ca `IfcSpace` tu file IFC va dua vao danh sach zone nang luong.

Sau do:

1. Moi zone deu duoc gan load dien.
2. Moi zone deu duoc allocate vao electrical board.
3. Dashboard va board summary cong tat ca zone lai.

Pipeline hien chua tach ro:

- Zone nao la **phong/khu vuc that de tinh dien**.
- Zone nao chi la **vung tong hop / gross area / context geometry**.

## 6. Huong xu ly de xuat

Khong nen xoa ngay cac zone lon, vi chung van co gia tri cho 3D view va thong tin IFC.

Huong an toan la them mot truong phan loai, vi du:

```text
energy_scope
```

Gia tri de xuat:

```text
atomic_energy_zone
```

Dung cho zone nho/phong that, duoc phep tinh dien va cong vao dashboard.

```text
aggregate_context
```

Dung cho cac zone lon nhu `VOLUME / OFFICE`, `GFA`, `HEATED NETAREA`. Cac zone nay chi giu lai lam ngu canh 3D/IFC/graph, khong dung de tinh tong dien, board load, KPI hoac ranking.

```text
review_required
```

Dung cho zone co dau hieu bat thuong nhung chua du can cu de loai tu dong, vi phong lon hoac vung ky thuat van co the la thermal zone hop le. Nhom nay mac dinh van duoc tinh dien cho den khi team review.

## 7. Cach trien khai an toan

De tranh lam thay doi so lieu dot ngot, nen lam theo tung buoc:

1. Danh dau cac zone nghi la aggregate/gross zone.
2. Chay song song hai bo so lieu:
   - So hien tai: `raw_total_kwh`.
   - So da loai trung: `deduped_total_kwh`.
3. So sanh chenh lech giua hai bo so.
4. Team review danh sach cac zone bi loai khoi tinh dien.
5. Sau khi thong nhat, moi chuyen dashboard sang dung so `deduped`.

## 8. Rui ro khi sua

Rui ro lon nhat la tong dien tren dashboard co the giam manh sau khi loai cac zone aggregate.

Dieu nay co the xay ra vi du lieu hien tai co the dang dat mot phan lon load vao cac zone lon. Neu chi bo cac zone nay ma khong phan bo lai load xuong zone nho, tong dien co the khong con khop voi building meter.

Vi vay khong nen fix bang cach xoa thang. Can danh dau, so sanh, va review truoc.

## 9. Trang thai sau khi da trien khai redistribute

Tinh den ngay 2026-06-30, huong xu ly da duoc trien khai tren production VM theo
che do `redistribute`, khong con chi la de xuat audit.

Mode dang chay:

```text
GREENFLOW_ENERGY_SCOPE_MODE=redistribute
GREENFLOW_TELEMETRY_SCOPE_MODE=redistribute
```

Ket qua reload telemetry:

```text
901,824 raw rows -> 843,264 effective rows
aggregate rows redistributed = 58,560
unmapped aggregates = 0
```

Sau reload, bang `telemetry_zone_15m` khong con row cho `aggregate_context`.
Dashboard va Run Optimization chi hien thi/count 288 zone:

```text
atomic_energy_zone = 210 zones
review_required = 78 zones
aggregate_context = 0 visible telemetry zones
```

Luu y quan trong:

- Tong energy effective duoc bao toan khi redistribute.
- Zone aggregate khong bi xoa khoi bang `zones`; chung duoc giu de audit/IFC context.
- API `/api/zones` va semantic agent da loc theo visible/countable zones, nen UI khong con hien cac zone lon nhu `VOLUME / OFFICE`, `GFA`, `Gross Area Placeholder`.
- Cac run agent cu trong DB van co log `308 zones`; chi run moi sau commit `ab7a944` moi hien `288 zones`.

Backup truoc khi reload telemetry:

```text
/root/greenflow_telemetry_zone_15m_before_redistribute_2026-06-30_151153.sql.gz
```

Checklist danh gia tiep:

1. Review file `docs/ZONE_ENERGY_SCOPE_REVIEW_LIST.csv`.
2. Xac nhan 20 `aggregate_context` da map dung child zone trong
   `data/knowledge_graph_build/mapping/zone_scope_child_weights.csv`.
3. Review tiep 78 `review_required`, dac biet cac zone co `scope_reason`
   la `context_space_name` hoac `unusual_height`.
4. Chay Run Optimization moi va xac nhan candidate actions khong target aggregate zone.
5. So sanh `/api/kpi/current`, `/api/kpi/health-score`, `/api/electrical/overview`
   voi dashboard de dam bao UI da dung so sau redistribute.

## 10. Ket luan

Hien tai co rui ro that su ve viec tinh trung nang luong giua zone lon va zone nho.

De xu ly dung, can tach ro:

- Zone dung de tinh dien that.
- Zone chi dung lam ngu canh hinh hoc/IFC.

Dashboard, board load va KPI khong nen cong truc tiep cac zone `aggregate_context`.
Production hien da chuyen sang redistribute: giu lai tong nang luong effective,
nhung chuyen tai/occupancy cua aggregate xuong child zones va an aggregate khoi
UI/agent surfaces.
