# AI Chat API — query historical building data (design)

Chatbot trả lời câu hỏi về **dữ liệu vận hành lịch sử** của tòa nhà (điện, chi
phí, peak, comfort, occupancy, alert). Mặc định dùng **Groq**; có cơ chế chọn
provider + nhập key (lưu mã hoá); lịch sử chat lưu DB; RAG bằng **turbovec**.

## Kiến trúc 1 lượt hỏi

```
user message
  → retrieve context (turbovec: policy/định nghĩa/Q&A cũ — ngữ nghĩa)
  → LLM (Groq, có tools)  ──tool_calls──►  data_tools (SQL THAM SỐ HOÁ trên telemetry)
  ◄── kết quả tool ───────────────────────┘   (lặp tối đa 4 vòng)
  → câu trả lời + trích nguồn
  → lưu user + assistant vào chat_messages
```

**Hai đường dữ liệu, tách bạch:**
- **Structured** (số liệu telemetry/KPI) → **function-calling** + SQL cố định
  (chính xác, an toàn). LLM chỉ chọn tool + điền tham số; KHÔNG sinh SQL tự do.
- **Unstructured** (định nghĩa, policy, tóm tắt report, Q&A cũ) → **vector RAG**
  (turbovec, ngữ nghĩa).

LLM chỉ điều phối + diễn giải; mọi con số đến từ tool (không bịa).

## Thành phần (backend/greenflow/)

| Module | Vai trò |
|---|---|
| `llm/provider.py` | `OpenAICompatibleProvider` — 1 client phủ Groq/OpenAI/OpenRouter/Together/Ollama (chỉ khác base_url). `make_provider()` factory. |
| `llm/keystore.py` | Mã hoá API key (Fernet) trước khi lưu DB. Không bao giờ lưu key trần. |
| `vector/embedder.py` | Sinh embedding (turbovec không tự sinh). Mặc định **bge-small-en-v1.5** (English). Fallback `hashing` (dev, không cần torch). |
| `vector/store.py` | Bọc turbovec `IdMapIndex` — add/search/remove/persist; id = id dòng `kb_chunks`. |
| `chat/data_tools.py` | 5 tool truy vấn lịch sử + schema function-calling. SQL tham số hoá. |
| `chat/service.py` | Orchestrator: retrieve + vòng tool-calling + lưu lịch sử. |
| `api/routers/chat.py` | Endpoints. |

## API

```
POST /api/chat                         {message, session_id?, building_id?}
                                       -> {answer, session_id, tools_used, sources}
GET  /api/chat/sessions                 danh sách phiên
GET  /api/chat/sessions/{id}/messages   lịch sử 1 phiên
POST /api/chat/kb/reindex               embed lại kb_chunks vào turbovec

GET  /api/llm/providers                  provider đã cấu hình + danh sách hỗ trợ
POST /api/llm/providers                  {provider, api_key, model?, base_url?}  (chọn + lưu, key mã hoá, set active)
POST /api/llm/providers/{id}/activate    chuyển provider đang dùng
```

## Chọn provider + nhập key + lưu (đúng yêu cầu sản phẩm)

`provider_configs` lưu: provider, model, base_url, **api_key_enc** (Fernet), is_active.
- POST `/api/llm/providers` với key → `encrypt_key()` → lưu, set active (tắt cái cũ).
- Lúc chat, `ChatRuntime.build()` lấy config active, `decrypt_key()` trong RAM, dựng provider.
- Chưa cấu hình gì → fallback `GROQ_API_KEY` trong env.
- Vì hầu hết provider là OpenAI-compatible, "đổi provider" = đổi 1 dòng config; Anthropic cần adapter riêng (đã chừa chỗ trong `make_provider`).

## Embedding model (sản phẩm tiếng Anh)

turbovec **không** sinh embedding → cần model ngoài. Khuyến nghị (English):

| Preset | Model | dim | Khi nào |
|---|---|---|---|
| **bge-small** (mặc định) | BAAI/bge-small-en-v1.5 | 384 | Cân bằng tốt nhất: nhẹ, nhanh, top MTEB retrieval. Chạy local, không tốn API. |
| bge-base | BAAI/bge-base-en-v1.5 | 768 | Cần chất lượng cao hơn, chấp nhận nặng hơn. |
| mxbai-large | mixedbread-ai/mxbai-embed-large-v1 | 1024 | Chất lượng cao nhất (local). |
| (API) | OpenAI text-embedding-3-small | 1536 | Nếu đã có key OpenAI, khỏi chạy local. |

bge/e5 **bất đối xứng**: query thêm prefix chỉ dẫn, passage thì không — embedder xử
lý qua `kind ∈ {query, passage}`. ⚠ `dim` embedder PHẢI khớp `dim` của turbovec
index; đổi model = reindex (`/api/chat/kb/reindex`). Groq KHÔNG có endpoint
embedding → phải dùng local (sentence-transformers) hoặc API khác.

## Schema (db/schema.sql, additive)

`provider_configs`, `chat_sessions`, `chat_messages`, `kb_chunks`. Vector KHÔNG
nằm ở Postgres — sống trong file turbovec (`storage/processed/vector/kb.tvim`),
`kb_chunks.id` (bigint) làm khoá tới `IdMapIndex`.

## Bảo mật

- API key provider **mã hoá Fernet** (master secret `LLM_KEYSTORE_SECRET` trong
  env, KHÔNG ở DB/Git). Hiển thị dạng mask `gsk_…CCqD0F`.
- `.env` đã gitignore; key Groq để trong `.env`, KHÔNG hardcode.
- ⚠ Key Groq dùng demo đã bị chia sẻ plaintext → **xoay key** sau hackathon.

## Đã kiểm chứng (end-to-end, DB thật + Groq live + turbovec)

- Q "How much energy today?" → tool `get_building_kpi` → "339.9 kWh, 815,760 VND" (số DB thật).
- Q "Which zone used most?" (đa lượt) → `get_top_consumers` → "Open Office, 313.5 kWh".
- Q "What does eco mode do?" → turbovec lấy đúng chunk → trả lời + nguồn.
- Lịch sử lưu DB; key mã hoá/giải mã round-trip; schema áp sạch (pg16).
- Provider Groq `llama-3.3-70b-versatile`; embedder bge-small (384) hoặc hashing(dev).
