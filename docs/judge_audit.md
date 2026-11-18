# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người | Reply/refund mâu thuẫn |
| 2 | H-017 | PASS | FAIL | Người | Claim hoàn sai bị bỏ lọt |
| 3 | H-029 | PASS | FAIL | Người | Trạng thái processing bị miss |
| 4 | H-042 | FAIL | PASS | Người | Judge nhìn nhầm reply hợp lệ |
| 5 | H-051 | FAIL | PASS | Người | Judge nhìn nhầm refund hợp lệ |

## Kết luận
- Tiêu chí helpful bị loại vì κ=0.375 (<0.6) và recall=0.300 (<0.7); 21 FN cho thấy bỏ lọt nhiều case.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
