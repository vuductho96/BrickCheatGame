# BrickCheatGame — Android và PC

App Android độc lập nằm trong [`android`](android/README.md): đọc màn hình,
tính nước và gửi cảm ứng trên điện thoại, không cần PC. APK được tạo qua
GitHub Actions → artifact **BrickCheatGame-debug**. Đây là bản thử nghiệm;
chưa có kiểm chứng rằng đạt điểm cao hơn trên game thật.

Bản PC và toàn bộ mã solver/vision/test vẫn được giữ ở thư mục gốc.
Cấu hình máy cá nhân, log phiên, công cụ tải về và môi trường Python
không được đẩy lên repo. Có mẫu cấu hình tại `config/settings.example.json`.
Ảnh màn hình và ảnh regression của phiên cá nhân cũng được giữ cục bộ.
Các test cần ảnh thật yêu cầu fixture riêng; test lõi và build Android chạy
được từ repo. APK thử nghiệm nằm tại `android/apk/BrickCheatGame-debug.apk`.

## Bản PC — Auto Local

Chạy độc lập trên PC, không dùng mô hình AI, API key hay dịch vụ AI. Không cần giữ Codex hoặc cuộc chat mở.

## Mở và dùng

1. Nhấp đúp **MO-AUTO-LOCAL.cmd** trong thư mục này.
2. Bật Gỡ lỗi không dây trên S23+, giữ PC và điện thoại cùng Wi-Fi. Mở game.
3. Chọn **Nhanh / Cân bằng / Kỹ**, rồi bấm **▶ Auto**.
4. Bấm **■ Dừng Auto** hoặc Esc để dừng. Nhấn trực tiếp lên màn hình LIVE cũng dừng Auto và chuyển sang thao tác tay.

Giao diện: http://127.0.0.1:8765. Bộ Python và thư viện đã được cài ở .venv trên PC này. Đây là bộ chạy local trong thư mục hiện tại; chuyển sang PC khác cần tạo môi trường Python và cài requirements.txt.

## Thuật toán

Nhận diện bàn 8×8 và khay bằng OpenCV từ video trực tiếp. Bộ tìm kiếm dùng bitboard và beam search; xét cả lựa chọn khối, thứ tự đặt và tọa độ của tối đa ba khối đang thấy.

Ưu tiên kế hoạch đặt hết khay; sau đó đánh giá số hàng/cột xóa, ô trống, vị trí còn đặt được các dạng khối, lỗ nhỏ và vùng trống bị chia cắt. Các dạng khối dùng trong điểm đánh giá chỉ đo độ thoáng của bàn, không phải dự đoán khay tương lai.

| Chế độ | Phương án giữ mỗi tầng | Ngân sách tính mỗi lượt | Kéo khối |
|---|---:|---:|---:|
| Nhanh | 60 | khoảng 180 ms | 300 ms |
| Cân bằng | 240 | khoảng 850 ms | 450 ms |
| Kỹ | 1.000 | khoảng 3 giây | 650 ms |

Thời gian trên là ngân sách tìm kiếm; lượt dễ hoặc được cache có thể kết thúc sớm. Chế độ Kỹ xét nhiều phương án hơn, không chỉ thêm thời gian chờ, nên có thể chọn nước khác. Tìm kiếm có giới hạn không bảo đảm tối ưu hoặc thắng mọi màn.

## Vòng Auto

- Đọc bàn ổn định và ba khối hiện tại.
- Tính kế hoạch, kiểm tra bàn chưa đổi rồi đặt một khối.
- Căn theo bóng xám/vùng nhận khối mà game vẽ trên lưới, thay vì căn hình khối nổi lệch với ngón tay. Hiệu ứng xóa hàng/cột được kiểm tra trước khi dùng căn theo hình khối.
- Chờ hiệu ứng xóa hàng, xác minh bàn thật và khay còn lại.
- Tính lại sau từng nước. Khi hết ba khối, đợi khay mới xuất hiện rồi tính từ khay đó.
- Nhận diện màn **TỐT LẮM**, bấm **Cấp độ tiếp theo** một lần và đợi cấp mới.
- Khi vị trí chưa khớp, trả khối về khay, tính lại hoặc chọn vị trí khác. Khi một khối đã đặt ở vị trí khác, đọc lại bàn thật rồi tính tiếp. Khi mất kết nối hoặc bàn chưa rõ, Auto chờ và tự tiếp tục khi dữ liệu trở lại. Khi thua, Auto dừng. Không tự tham gia lại và không tự dùng vật phẩm.

Ô có biểu tượng đá quý vẫn được nhận diện là ô có gạch. Bộ giải hiện dùng mục tiêu xóa hàng/cột và giữ bàn thoáng; chưa có OCR đếm mục tiêu đá quý.

## Màn hình trực tiếp

scrcpy 5.0.1 chính thức mã hóa H.264 540×1170, tối đa 20fps, 2.5Mbps. Python giải mã rồi truyền khung qua WebSocket vào canvas HTML. Input truyền qua socket điều khiển scrcpy, không dùng chuỗi lệnh ADB cho mỗi lần di chuột.

Không dùng screencap để cập nhật màn hình. Luồng ở RAM; chỉ khi kéo lỗi có thể lưu một ảnh chẩn đoán vào artifacts. Điện thoại đã được tăng screen_off_timeout từ 30000 lên 2147483647 ms theo yêu cầu tránh tự khóa.

## Kiểm tra

164 tests pass: bóng xám từ ảnh lỗi của người dùng, sửa lệch một hàng bằng điện thoại mô phỏng, không phát gợi ý cũ lúc kéo, không phục vụ bàn cũ khi dữ liệu hết hạn, tự tính lại sau lỗi vị trí, luật xóa hàng/cột, solver đối chiếu oracle nhỏ, khay mới chỉ được tính sau khi quan sát, nhận diện màn thắng/thua, chuyển cấp không bấm lặp, ô có đá quý, theo dõi khối và dừng trước input.

Đã xác minh video và kéo thủ công thật; đã thử Auto đặt khối 3×3, đặt các nước được kiểm tra khớp trên S23+, và chuyển từ màn thắng cấp 6 sang cấp 7. Sau yêu cầu dừng thử, không chạy thêm lượt trên điện thoại. Đây không phải chứng nhận thắng toàn bộ cấp.

Cầu nối chỉ mở 127.0.0.1, có token phiên và kiểm tra Origin. Nút Auto khởi động thuật toán trên máy, không gửi dữ liệu tới AI.

Source chính: autopilot.py, live_mirror.py, live_socket.py, web_bridge.py, web/auto.js.
scrcpy: https://github.com/Genymobile/scrcpy
Tài liệu tham khảo tìm kiếm block puzzle: https://informatika.stei.itb.ac.id/~rinaldi.munir/Stmik/2024-2025/Makalah2025/Makalah-IF2211-Strategi-Algoritma-2025%20(62).pdf

Bản auto-local-2: bộ quan sát độc lập cập nhật bàn ổn định từ video khoảng mỗi 120ms; giao diện hỏi trạng thái mỗi 350ms. Khi đang kéo/thả, gợi ý cũ được ẩn và hiện nước đang thực hiện. Auto và gợi ý sử dụng cùng bộ giải/chế độ. Kiểm tra giao diện chỉ đọc ghi nhận tuổi khung bàn 0.16 giây, không có lỗi JavaScript hoặc input điện thoại; không thử thêm ván trên điện thoại sau yêu cầu dừng thử.


Chiến lược điều khiển tự thích nghi và giới hạn: [AUTO-LOCAL.md](AUTO-LOCAL.md). Bản auto-local-3 đo lại phản ứng hình ảnh trong mỗi lần kéo, theo dõi viền ô để tránh biểu tượng giữa ô, kiểm tra khung mới và tự phục hồi sau lỗi căn.


Bản auto-local-4 bỏ quyền nhả dựa trên hình nổi; cần ô nhận đúng từ game. Thả sai bàn dự tính gây dừng Auto và lưu auto-moves.jsonl.

Bản auto-local-5: nắm ô có gạch gần tâm nhất; khóa mục tiêu cho bàn/khay không đổi; không đổi sang phương án thứ hai khi căn lỗi. Ảnh ngay trước nhả lưu ở artifacts/auto-before-release.png, cùng sự kiện release_authorized và tọa độ con trỏ trong auto-moves.jsonl. Đây là dữ liệu chẩn đoán, chưa chứng minh lỗi lệch cột trên điện thoại thật đã được loại bỏ.
