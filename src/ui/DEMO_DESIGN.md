# Thiết kế demo trực tiếp

Trạng thái: đề xuất chưa triển khai. Theo yêu cầu tiếp theo, UI hiện ưu tiên so sánh trực quan và giải thích lựa chọn kiến trúc từ benchmark; xem `README.md`. Phần backend và chạy trực tiếp dưới đây được để dành nếu nhóm cần bổ sung sau.

## Mục đích

Cho nhóm chạy tình huống trực tiếp và giải thích quyết định, các bước thực thi, ledger và audit. Benchmark và crash report hiện có tiếp tục dùng để tổng kết kết quả.

## Hướng triển khai đề xuất

Thêm server Python dùng thư viện chuẩn trong `src/ui/`, vừa phục vụ UI vừa gọi `lab8.app.prepare_store` và `run_shape`. Không sửa shape, policy, durability, metrics hoặc báo cáo của nhóm.

Đã cân nhắc: chỉ chạy CLI rồi nhập JSON ít thay đổi hơn nhưng không cho tương tác trực tiếp; framework API riêng cần thêm dependency. Server Python nhỏ phù hợp phạm vi demo local và môi trường hiện có. Đây là phương án đề xuất để người dùng duyệt.

## Màn hình

Thêm mục **Demo trực tiếp** bên cạnh Benchmark và Crash safety.

- Chọn shape, claim công khai và seed; giải thích ngắn tình huống bằng dữ liệu được chọn lọc.
- Chọn điểm crash: không crash, trước effect, sau effect trước checkpoint, sau checkpoint.
- **Chạy tình huống mới**: tạo database demo riêng và thực thi một lần.
- **Chạy lại / Resume**: giữ database của tình huống hiện tại, chạy lại cùng claim và shape, không chèn crash.
- **Đặt lại**: bỏ phiên demo hiện tại để bắt đầu mới.

Hiển thị ba vùng chính:

1. **Quyết định**: status, tiền đề xuất, tiền thực hoàn, run ID, model/tool calls và chi phí mô phỏng. Nếu có crash, hiển thị rõ đã gián đoạn, không giả lập một RunResult thành công.
2. **Các bước thực thi**: sự kiện trace được chọn lọc và giải thích; không tuyên bố đây là suy nghĩ nội bộ của model. Với crash, chỉ hiển thị trace thực sự có và ghi rõ nếu trace chưa được ghi.
3. **Trước / Sau**: số refund, tổng tiền của claim, số audit refund_committed, trạng thái checkpoint. Giữ kết quả từng lần chạy để minh họa retry không tạo refund trùng.

## Kịch bản trình bày

- Hoàn tiền hợp lệ → retry → refund và audit vẫn chỉ có một.
- Crash sau effect trước checkpoint → thấy effect đã tồn tại → resume → không tạo refund trùng, checkpoint được hoàn tất.
- Approval thiếu hoặc không hợp lệ → không phát sinh refund.
- Chạy cùng tình huống trên các shape để giải thích sự khác biệt qua trace; swarm là đối chứng có thể sai, không tự sửa kết quả.

## Ranh giới dữ liệu

Database và trace demo nằm trong thư mục tạm riêng của server, tách khỏi reports và trace dùng làm bằng chứng. Retry dùng cùng store; tình huống mới dùng store mới. Chỉ lắng nghe localhost. Chỉ nhận shape/claim/seed/crash point hợp lệ, không nhận đường dẫn tùy ý từ trình duyệt.

API chỉ trả field được phép hiển thị, không trả raw claim/order, ticket thô, secret, header, PII hoặc raw exception. Trace phải được chọn lọc và kiểm tra trước khi trả về. Không tính nhãn expected là kết quả thực thi. UI ghi rõ backend của lab là MockLLM và chi phí mô phỏng.

## Kiểm tra

Kiểm tra API chạy thật: claim hợp lệ, retry cùng claim, crash rồi resume, approval bị từ chối, đầu vào không hợp lệ và dữ liệu trả về không chứa secret/PII. Chạy lại test UI và pytest của lab sau khi tích hợp. Hướng dẫn khởi động bằng đường dẫn theo vị trí script để tránh lỗi thư mục làm việc trước đây.
