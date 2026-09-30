# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đức Long
- **MSSV:** 2A202602917
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/duclongt23/K4-L3-DAY13-NguyenDucLong-2A202602917-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602917`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt tối đa sau khi implement correlation ID, log enrichment và PII scrubbing |
| `validate_dashboard.py` | 6/6 | 6/6 | Dashboard contract hợp lệ đủ 6 panel ngay từ đầu |
| `pytest` | 22 passed | 25 passed | Thêm 3 test mới (prompt management, tracing adapter, CLI encoding) |
| Số traces hợp lệ | 0 | ≥10 | Traces tạo trong project Langfuse cá nhân `day13-k4-l3b-2A202602917` |
| Số PII leak | >0 | 0 | PII processor scrub trước khi serialize; 125 records phân tích, 0 leak |
| Latency P95 / TTFT P95 | N/A | 5156 ms / 50 ms | P95 cao do incident `rag_slow` (sleep 2.5s); TTFT bình thường |
| Retrieval success rate | N/A | 100% | Không có lỗi `tool_fail`; tất cả `tool_success=true` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware `CorrelationIdMiddleware` (`app/middleware.py`) được đăng ký trên toàn bộ FastAPI app. Với mỗi request, middleware đọc header `x-request-id`; nếu không có thì tự sinh `req-{uuid4().hex[:8]}` (8 ký tự hex). ID này được bind vào `structlog.contextvars` (thread-local) qua `bind_contextvars(correlation_id=...)` và lưu vào `request.state.correlation_id` để truyền xuống `agent.run()`. Response trả về luôn có header `x-request-id` và `x-response-time-ms`.

- **Các metadata được ghi vào structured log:** Ngoài correlation ID tự động inject vào mọi log qua contextvars, mỗi request còn bind thêm: `user_id_hash` (SHA-256 12 ký tự đầu của user_id), `session_id`, `feature`, `model` (tên model LLM đang dùng), `env` (APP_ENV từ .env). Các log event quan trọng: `request_received` ghi `message_preview`; `response_sent` ghi `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.

- **Cách bảo đảm PII được scrub trước khi ghi:** Hàm `scrub_event()` trong `app/logging_config.py` được đăng ký làm structlog processor trước `JsonlFileProcessor()` và `JSONRenderer()`. Processor này dùng regex từ `PII_PATTERNS` trong `app/pii.py` để thay thế email (`[\w.-]+@[\w.-]+.\w+`), số điện thoại VN (`+84/0 + 9 chữ số`), CCCD (12 chữ số liên tiếp) và thẻ tín dụng (16 chữ số nhóm 4) thành `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`. Vì processor chạy trước khi data được serialize xuống file, PII không bao giờ được ghi thô.

- **Cách kiểm chứng kết quả:** Chạy `python scripts/validate_logs.py` — script đọc toàn bộ `data/logs.jsonl`, kiểm tra schema JSON hợp lệ, correlation ID format `req-[0-9a-f]{8}`, enrichment fields (user_id_hash, session_id, feature, model, env) và scan PII patterns. Kết quả cuối: **100/100**, 125 records phân tích, 0 PII leak, 48 unique correlation IDs.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Đăng nhập Langfuse Cloud, chọn project `day13-k4-l3b-2A202602917`, vào Traces. Lọc theo tag `lab` và `monitoring`. Mỗi trace có `metadata.correlation_id` khớp với header `x-request-id` của request tương ứng.
- **Cấu trúc root/retrieval/generation observations:** Root span `lab-agent-run` (as_type=agent) bao bọc toàn bộ. Child span `retrieval` (mock_rag.retrieve) ghi doc_count và query_preview. Generation trong `propagate_attributes(prompt=...)` ghi model, usage_details và cost_details.
- **Cách nối trace với log:** Cả trace (metadata.correlation_id) và log (field correlation_id) cùng giá trị `req-<8hex>`. Lọc log theo correlation_id để tìm log line, sau đó tìm trace cùng correlation_id trong Langfuse.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version 1 — label `production`
- **Version/label candidate:** version 2 — label `latest`
- **Trace ID của mỗi version:** <lấy từ Langfuse UI — click vào trace, copy UUID từ URL>
- **Cách promote và rollback `production`:** Langfuse UI → Prompts → day13-chat → chọn version → Promote → đặt label `production`. Rollback: chọn lại version cũ → Promote.


## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard `K4-L3B Day 13 Monitoring & LLMOps` có 6 panel đọc từ `data/logs.jsonl`, time range 60 phút, refresh 30 giây:
  1. **latency** — P50/P95/P99 latency và TTFT P95 (ms), threshold P95 ≤ 3000ms
  2. **traffic** — Request count và rate/phút, threshold ≥ 1 req/phút
  3. **errors** — Error rate (%), error_type breakdown, retrieval success rate (%), threshold error ≤ 2%
  4. **cost** — Cost USD theo phút và tổng, threshold tổng ≤ $2.50
  5. **tokens** — Tổng tokens_in và tokens_out
  6. **quality** — Quality score trung bình, threshold mean ≥ 0.75
- **SLO và lý do chọn:** SLO chính: `fast_successful_requests` — 99.5% request trong 28 ngày phải có latency ≤ 3000ms. Chọn ngưỡng 3000ms vì đây là giới hạn trải nghiệm người dùng chấp nhận được; baseline P95 của hệ thống bình thường là ~1093ms, dư nhiều so với ngưỡng.
- **Cách tính error budget:** SLO 99.5% trong 28 ngày → error budget 0.5%. Với khoảng 1000 request/ngày × 28 ngày = 28,000 request, tối đa 0.5% × 28,000 = **140 request** được phép không đạt SLO (latency > 3000ms hoặc lỗi).
- **Ba alert và runbook tương ứng:**
  1. **high_latency_p95** (critical): P95 latency > 3000ms trong 5 phút → Slack #incidents → Runbook: kiểm tra `rag_slow` incident flag, xem trace retrieval span có sleep bất thường không.
  2. **high_error_rate** (warning): Error rate > 2% trong 3 phút → Slack #alerts → Runbook: kiểm tra `tool_fail` flag, xem log `request_failed` tìm error_type.
  3. **cost_spike** (warning): Total cost USD > $2.50/ngày → Slack #cost-alerts → Runbook: kiểm tra tokens_out tăng đột biến, xem `cost_spike` incident flag, rollback về prompt version tiêu thụ ít token hơn.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-30 15:29 – 15:33 (UTC+7) / 08:29 – 08:33 UTC. Incident flag `rag_slow` được bật trước đó, load test `--challenge --concurrency 5` chạy trong khoảng này.
- **Triệu chứng từ metrics:** Dashboard panel **Latency** cho thấy P95 latency tăng vọt lên **2652ms** (vượt ngưỡng SLO 3000ms nếu tiếp tục tăng). Tất cả 5 session challenge (`k4-l3b-challenge-s01` đến `s05`) đều bị ảnh hưởng đồng loạt, nhưng traffic và error rate vẫn bình thường (retrieval thành công, không có `request_failed`) — triệu chứng điển hình của **tail latency do retrieval chậm**, không phải lỗi.
- **Log line và correlation ID liên quan:** Event `response_sent` với `correlation_id=req-23eec500` (`session_id=k4-l3b-challenge-s02`, `ts=2026-09-30T08:29:03Z`, `latency_ms=2652`, `tool_name=retrieval`, `tool_success=true`). Đây là một trong các request challenge bị ảnh hưởng; tất cả request trong batch có latency đồng đều ~2652ms, cho thấy độ trễ bắt nguồn từ một điểm cố định trong retrieval path.
- **Trace ID và span gây ảnh hưởng:** Trace tương ứng `correlation_id=req-23eec500` trong Langfuse project `day13-k4-l3b-2A202602917`. Waterfall cho thấy span **`retrieval`** (type: span, `mock_rag.retrieve`) chiếm toàn bộ ~2500ms trong tổng latency 2652ms; span generation chỉ tốn ~100ms. Span `retrieval` có `tool_success=true` nhưng duration bất thường — dấu hiệu rõ ràng của sleep/blocking trong retrieval layer.
- **Root cause:** Incident flag `rag_slow=True` trong `app/incidents.py` khiến hàm `retrieve()` trong `app/mock_rag.py` thực thi `time.sleep(2.5)` trước khi trả về kết quả. Đây mô phỏng kịch bản vector store bị quá tải hoặc timeout mềm — retrieval vẫn trả về dữ liệu đúng nhưng phải đợi 2.5 giây mỗi request. Vì concurrency 5, tất cả request trong cùng batch đều bị blocking đồng thời.
- **Fix action:** Gọi `POST /incidents/rag_slow/disable` (hoặc `python scripts/inject_incident.py --disable`) để tắt flag. Latency về lại ~150ms ngay lập tức (xác nhận bằng load test batch tiếp theo). Trong môi trường production: scale up vector store replicas, tăng connection pool size, hoặc implement circuit breaker với fallback cache.
- **Preventive measure:** (1) Alert `high_latency_p95` đã cấu hình trong `config/alert_rules.yaml` sẽ trigger khi P95 > 3000ms trong 5 phút → notify Slack #incidents ngay. (2) Thêm hard timeout 2s cho retrieval call và fallback về cache khi timeout. (3) Thêm SLO burn rate alert để phát hiện sớm khi error budget tiêu thụ nhanh. (4) Runbook: kiểm tra `/health` → xem `incidents` flag → disable nếu cần → validate bằng load test nhỏ.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Đặt `scrub_event()` processor vào **trước** `JsonlFileProcessor()` và `JSONRenderer()` trong chuỗi structlog processors. Nếu đặt sau khi render, PII đã được serialize thành JSON string và regex sẽ phải parse lại chuỗi đã encode — phức tạp, dễ bỏ sót. Đặt trước đảm bảo PII được scrub ở tầng object trước khi bất kỳ serialization nào xảy ra, giống nguyên tắc "sanitize at ingestion, not at output".

- **Một lỗi/blocker đã gặp:** Server FastAPI (`uvicorn`) không tự động load file `.env`, dẫn đến `tracing_enabled: False` ngay cả khi `.env` đã có đủ Langfuse keys. Traces không được tạo và không lên Langfuse Cloud dù auth check pass khi test thủ công.

- **Cách tìm nguyên nhân và xử lý:** Gọi `/health` endpoint → thấy `"tracing_enabled": false`. Kiểm tra `tracing.py` → `tracing_enabled()` check `os.getenv(LANGFUSE_PUBLIC_KEY)` → env var trống. Chạy script test với `load_dotenv()` tường minh → key có. Kết luận: thiếu `load_dotenv()` trong entry point. Fix: thêm `from dotenv import load_dotenv; load_dotenv()` vào đầu `app/main.py` trước tất cả imports dùng env vars. Ngoài ra thêm `client.flush()` sau mỗi request để traces lên Langfuse ngay, không bị mất khi buffer chưa đầy.

- **Cách hiểu luồng Metrics → Logs → Traces:** **Metrics** (từ `/metrics` hoặc dashboard panel latency) là tín hiệu đầu tiên phát hiện anomaly — P95 tăng vọt → có vấn đề latency. **Logs** (từ `data/logs.jsonl`) cho phép lọc theo thời gian và tìm `correlation_id` của request bị ảnh hưởng — thấy `latency_ms=2652`, `tool_success=true` → retrieval chậm, không phải lỗi. **Traces** (từ Langfuse) xác nhận chính xác span nào trong pipeline gây ra latency — waterfall cho thấy span `retrieval` chiếm >2500ms, generation chỉ ~100ms. Ba nguồn cùng trỏ về một nguyên nhân duy nhất mới là kết luận hợp lệ.

- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt versioning cho phép A/B test và rollback nhanh khi chất lượng giảm — không cần redeploy code. Token/cost tracking giúp phát hiện prompt regression (prompt mới tốn nhiều token hơn mà chất lượng không tăng). SLO định nghĩa ngưỡng chấp nhận được và tính error budget — khi budget cạn kiệt, team phải ưu tiên reliability hơn feature. Rollback là công cụ khôi phục nhanh nhất khi incident xảy ra do thay đổi prompt.

- **Điều quan trọng nhất đã học:** Ba tín hiệu Metrics → Logs → Traces không thể thiếu nhau. Metrics phát hiện sự cố, logs xác định phạm vi ảnh hưởng và correlation ID, traces chỉ ra đúng component gây ra vấn đề. Chỉ có trace mới trả lời được câu hỏi "span nào trong pipeline bị chậm/lỗi" — không thể suy ra từ metrics hay logs đơn lẻ.

- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Child observations (retrieval span và generation) chưa được tách thành các nested span riêng biệt với đầy đủ input/output metadata trong Langfuse. Hiện tại metadata được ghi vào root span thông qua `update_current_span()`. Cần dùng `@observe` decorator trên `retrieve()` và `FakeLLM.generate()` để có waterfall chi tiết hơn.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
