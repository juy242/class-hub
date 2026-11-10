# Báo cáo đánh giá AI

Sinh tự động bởi `make eval` (`eval/run_all.py`). **Đừng sửa tay.**

- Thời điểm chạy: 2026-11-09 16:59 +0000
- Model LLM: gemini-flash-lite-latest
- Phiên bản lời nhắc: Trợ lý `system_v1.vi`, Nhận xét `reports-v1`

## Kết quả theo DESIGN mục 12

| Thành phần | Chỉ số | Kết quả | Mục tiêu | Đạt? |
| --- | --- | --- | --- | --- |
| 1. Tính điểm Thông tư 22 | 30/30 = 100% | — | 100% | ĐẠT |
| 2. Trợ lý hỏi dữ liệu | đúng hàm 4/4 = 100%; đúng số 4/4 = 100%; từ chối — <br><sub>mẫu nhỏ A09,A13,A24,A32 (hạn mức free); bộ 50 câu chạy khi có khóa trả phí</sub> | — | ≥ 85% | ĐẠT |
| 3. RAG văn bản quy định | Hit@4 29/30 = 97%; từ chối 5/5 = 100% <br><sub>“% trả lời đúng” cần LLM (đo qua bộ Trợ lý, các câu quy định)</sub> | — | ≥ 80% | ĐẠT |
| 4. Mô hình cảnh báo | Recall 0.92 | — | Recall ≥ 0,75 | ĐẠT |
| 5. Nhận xét do AI viết | — <br><sub>chạy comments_gen.py để sinh CSV, cho giáo viên chấm, rồi comments_eval.py</sub> | — | TB ≥ 4; 0 câu tiêu cực | chờ giáo viên chấm |
| 6. Phân quyền & bảo mật AI | 3/3 = 100% <br><sub>mẫu nhỏ SEC04,SEC12,SEC14 (hạn mức free); bộ 20 câu chạy khi có khóa trả phí</sub> | — | 100% | ĐẠT |

Ghi chú:
- Số đo tính trên dữ liệu giả lập (`data/seed/`), đã scope theo năm học hiện hành.
- Mẫu còn nhỏ: con số để theo dõi xu hướng, chưa đủ kết luận thống kê.
