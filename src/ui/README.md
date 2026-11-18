# ChocoMint UI

Giao diện đọc báo cáo của Lab 08, dùng HTML/CSS/JavaScript thuần, không cần cài thư viện.

## Chạy

Từ thư mục gốc repo:

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory src
```

Mở <http://localhost:8000/ui/>. Cần chạy qua HTTP để trình duyệt tải module và báo cáo; không mở trực tiếp `index.html` bằng `file://`.

## Dùng khi thuyết trình

1. Mở Benchmark, kiểm tra nhãn báo cáo thật rồi bấm **Chế độ trình bày** để ẩn thanh bên và mở rộng vùng so sánh. Bấm Esc để trở về.
2. Giới thiệu đề xuất ở đầu trang: shape có chi phí/thành công thấp nhất trong các shape đạt ngưỡng pass rate, được chấm đầy đủ và cùng tập claim × seed. Có thể đổi ngưỡng 100% / 99% / 95% và shape đối chiếu chi phí.
3. Đối chiếu biểu đồ chi phí (cùng thang từ 0) với pass rate và pass⁵ (cùng thang 0–100%). Sau đó xem số bước, model calls và tool calls ở bảng.
4. Chọn claim và seed ở **Đối chiếu cùng tình huống** để xem bốn kết quả cạnh nhau. Đây là dữ liệu đã ghi trong benchmark, không thực thi lại shape.
5. Mở Crash safety để trình bày bằng chứng crash suite chung. UI không gán kết quả suite này thành chứng nhận riêng cho từng shape, không suy ra approval/secret/hidden đã đạt.

Đề xuất chỉ là so sánh kinh tế trên benchmark public với MockLLM và chi phí mô phỏng, không tự ghi quyết định ADR. Trường hợp đồng chi phí sẽ hiện đồng hạng; thiếu dữ liệu hoặc khác bộ thử nghiệm thì không chọn shape. Chênh lệch phần trăm dùng chi phí của shape đối chiếu làm mẫu số.

## Tích hợp báo cáo

- UI đọc `src/reports/benchmark.json` và `src/reports/crash.json` khi mở trang hoặc bấm **Nạp báo cáo mới**.
- Chạy các lệnh sinh báo cáo trong `src/reports/README.md` từ thư mục `src/`. Không cần sửa UI khi báo cáo xuất hiện; bấm nạp lại.
- Hoặc mở mục Benchmark / Crash safety tương ứng rồi chọn file JSON từ máy. File chỉ được đọc trong trình duyệt, không tải lên dịch vụ nào.
- Hai báo cáo có nguồn riêng. Khi thiếu file, mục tương ứng dùng dữ liệu mẫu từ `sample.js`, có nhãn rõ. Khi nạp lại thất bại, giữ báo cáo trước đó và hiển thị thông báo.
- Mẫu chỉ để dựng UI, không dùng làm bằng chứng nộp bài và không ghi vào `src/reports/`.

## Hợp đồng dữ liệu

Benchmark theo `lab8/benchmark.py`: `controlled_variables`, `by_shape`, `trials`. UI dùng `pass_rate`, `pass_5`, `seed_variance`, `cost_per_success_vnd`, `mean_steps`, `mean_model_calls`, `mean_tool_calls` và `graded_trials`. Trial có `shape`, `claim_id`, `seed`, `passed`, `status`, `reason`, `cost_estimate`, `run_id`.

Crash theo `lab8/crash_test.py`: `count`, `passed`, `scenarios` với `id`, `point`, `passed` (boolean), `reason`. Số lượng và số kịch bản đạt phải khớp tổng hợp.

`null` hoặc thiếu chỉ số hiển thị `—`. Trial `passed: null` là chưa chấm; không tính là thất bại. Chi phí mô phỏng VND, không hiển thị latency giả.

## Thiết kế và kiểm tra

Theo hướng đã chốt: dashboard đọc báo cáo với bảng so sánh 4 shape, lọc lần chạy và màn hình crash safety. Màu chocolate `#49352c`, mint `#d0ebdf`, nền `#f6f7f5`, chữ phụ `#716e67`, trạng thái lỗi `#953a2e`. Dùng Segoe UI hỗ trợ tiếng Việt; thanh điều hướng bên trái, nội dung căn trái, bảng cuộn ngang trên điện thoại. Màu trạng thái luôn đi cùng nhãn chữ.

Triển khai: kiểm tra schema và bộ lọc → mẫu riêng → giao diện → nạp JSON và xử lý lỗi → kiểm thử. Phạm vi chỉ `src/ui/`, không thay đổi shape, ledger hoặc báo cáo của nhóm.

Chạy test đọc dữ liệu, bộ lọc và trường hợp chưa chấm bằng Node.js 18+:

```powershell
node --test src/ui/report.test.mjs src/ui/integration.test.mjs
```

Test tích hợp đọc trực tiếp hai báo cáo thật và đối chiếu tổng hợp với từng trial. Nếu chưa sinh báo cáo, test tương ứng được đánh dấu bỏ qua. Không chỉnh tay báo cáo để làm test đạt.
