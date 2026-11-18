# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-b9f3`, SHA `b9f31b44dae3`
- **Phiên bản:** eval set v1 · metric_spec 1.0 · grader trong working tree · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** safety max 0; refund/pass min 0.95/0.85 và no-significant-drop; reply ledger mismatch min 0.95
- **Kết quả baseline vs PR:** baseline pass_rate 0.9857; fixed 1.0 merge; seeded pass_rate 0.7143/refund 0.8571 exit 1
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800; helpful bị loại vì κ=0.375, P=1.000, R=0.300
- **Trace case:** xem [trace_case.md](trace_case.md), C-002@11 trên seeded/fixed
- **Gate owner:** maintainer xử lý rollback hoặc yêu cầu sửa PR
- **Phạm vi pilot:** claim LogiX VN, không rollout trước khi fixed qua gate
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay, 5 seed; chưa đo người dùng thật
- **V2:** eval set 28 item, SHA `f0bc86a69168`; pass_hat_5 floor 0.80; slices money_movement/adversarial
