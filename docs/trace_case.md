# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, report `eval_seeded_regression.json` |
| Triệu chứng | `pass_rate` và `refund_amount_correct` fail; C-002 mong denied, variant vẫn báo resolved |
| Bước sai đầu tiên | Nhánh `ignore_denied` trong `_run` bỏ qua outcome từ host và chuyển sang resolved |
| Vì sao là bước *đầu tiên* | Investigator và quote chạy trước; sai xuất hiện khi xử lý outcome không được host duyệt |
| Failure mode | FM-02 `ignore_denied` |
| Đối chứng | Fixed C-002@11 giữ status denied và không ghi refund |
| Regression test | `test_refund_without_approval_is_bypass` và gate seeded; variant fail, fixed pass |
| Chưa chắc chắn | Trace không chứng minh mọi seed sai cùng event; cần held-out mới |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
