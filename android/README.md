# Bric Android

App độc lập cho Android 13 trở lên. Không cần PC, Wi-Fi, ADB, API key hay
quyền root khi sử dụng. Không có quyền INTERNET trong manifest.

## Cài và chạy

Bản 1.0.10 loại các ô vốn đã có trên bàn khỏi phép nhận dạng vùng đặt,
để màu xem trước xóa hàng/cột không bị coi là các ô của khối mới. Ảnh lỗi
kéo lưu đúng khung mà bộ căn vừa kiểm tra. Bản 1.0.9 đã xác minh một nước
trong ván thật nhưng dừng ở nước có hiệu ứng tô lại ô cũ.

Bản 1.0.9 bổ sung xác nhận hình che bóng xám: phải có đủ mọi ô mới của
khối ở tâm lưới, không chấp nhận chỉ một phần hình. Luồng capture không
tìm viền trong lúc Auto kéo; mỗi chuyển động chờ 220 ms để ảnh theo kịp.
Trước đó bản 1.0.8 đã xác minh một nước thật, nhưng còn kẹt với khối 3×3
che bóng. Khi kiểm tra Auto không chạy `uiautomator dump`: công cụ đó có
thể tạm ngắt các dịch vụ Trợ năng và hủy cử chỉ đang giữ.

Bản 1.0.7 căn theo vùng xám mà game đã bắt vào lưới, thay vì coi vị trí
hình màu nổi là ô sẽ nhận. Chỉ nhả khi tìm được duy nhất vùng xám khớp
hình và trùng đích hai lần; không nhả chỉ vì hình màu trông đã gần đích.
Kiểm thử trên ảnh lỗi S23+ xác định đúng hàng 3, cột 7 dù hình màu bị cắt
ở mép màn hình. Log `alignment` lưu vị trí tay, đích và vùng quan sát.

Bản 1.0.6 đọc pixel vào bộ nhớ một lần, kiểm tra màu viền và khay bằng RGB
thay cho gọi Bitmap/HSV từng pixel. Trên S23+, ảnh bàn thật được đọc đúng
ma trận và ba khối trong 526 ms; hai fixture tổng hợp cũng đạt. Trạng thái
chờ bàn ghi số lần đọc ổn định và thời gian đọc, thay vì báo sai “Chưa có ảnh”.
Xuất log kèm `drag-unreadable.png` khi không tìm được hình đang kéo.

Bản 1.0.5 giữ ảnh cuối trong đợt cập nhật: chờ thời điểm đọc thay vì lấy
ảnh ra rồi bỏ qua trong khoảng giới hạn tốc độ. Có 3 kiểm thử lịch đọc
ảnh, ngoài 9 kiểm thử solver. Đưa khối vào giữa bàn trước khi căn, lưu
`drag-unreadable.png` nếu không theo dõi được khối trong lúc kéo. Kết quả
kiểm thử chưa chứng minh kéo trong game thật đã thành công.

Bản 1.0.3 phục hồi tham chiếu dịch vụ Trợ năng theo vòng đời Android,
không để dịch vụ cũ xóa trạng thái của dịch vụ mới. Hiệu chỉnh không
vuông được bỏ qua để dùng viền bàn tự tìm. Chưa có lượt kéo thật xác
minh thành công cho các bản sửa này; cần đối chiếu log khi dùng Auto.

Bản 1.0.2 tìm viền dưới khay để không lấy nút hỗ trợ vào hình khối,
lưu `error.png` khi nhận dạng thất bại. Đã đọc được bàn và ba hình trong
ảnh ván thật đang mở, cùng hai fixture tổng hợp; vẫn cần kiểm tra kéo
trực tiếp để kết luận Auto hoạt động.

Bản 1.0.1 sửa việc chờ khung mới khi màn hình đứng yên: giữ ảnh gần nhất
để đọc bàn, nhưng sau thả phải có ảnh mới hơn ảnh trước nhả. Khi kéo,
đếm khung từ trước lệnh di chuyển; xác nhận đích lần hai dùng dịch một
pixel để tạo thay đổi. Luồng capture chỉ tìm viền cho hiệu chỉnh mỗi giây.
Lỗi đọc cụ thể được giữ lại trong trạng thái và log.

1. Cài `BrickCheatGame-debug.apk` (bản thử nghiệm, ký bằng khóa debug).
2. Mở Bric, bấm **Bật Trợ năng Bric**, bật dịch vụ trong Cài đặt Android.
3. Bấm **Chia sẻ toàn bộ màn hình** và xác nhận trong hộp thoại hệ thống.
   Chọn toàn màn hình, không chỉ cửa sổ Bric hoặc một ứng dụng.
4. Mở một ván game, quay lại Bric và bấm **Chạy Auto trên điện thoại**.
   Bric lùi xuống nền; cần để bàn game ở phía trước trong vòng 10 giây.
5. Dừng bằng nút trong thông báo hoặc quay lại Bric. Nếu đổi hướng hoặc
   độ phân giải, tắt chụp màn hình rồi cấp lại phiên mới.

Có thể mở game rồi chọn **Chạy Auto** trong thông báo Bric. Cách này
không cần đưa Bric ra trước bàn game. Android 14 trở lên được yêu cầu
capture toàn màn hình, tránh chỉ thu cửa sổ Bric. Cập nhật APK hoặc
dừng phiên capture sẽ cần xác nhận chia sẻ màn hình lại.

Hiệu chỉnh tùy chọn: sau khi mở bàn vài giây, quay lại Bric, chọn
**Hiệu chỉnh / xem bàn**. Chạm hai góc bên trong bàn, không bao gồm viền.
Chọn **Tự tìm viền** để bỏ hiệu chỉnh. **Lưu log** xuất ZIP qua trình chọn
tệp Android; log và ảnh lỗi nằm trên máy, không được gửi tự động.

## Cách tính mới

- Bitboard 64 bit, hình bất kỳ biểu diễn bằng tọa độ ô, không tra tên hình.
- Tìm thứ tự và vị trí của ba khối thật, có vét cạn giới hạn để cứu trường
  hợp beam search bỏ sót. Hết ngân sách không được coi là chứng minh thua.
- Đánh giá tất cả kích thước hình chữ nhật trống trong bàn 8×8: một vùng
  trống h×w chứa được mọi hình có hộp bao không lớn hơn h×w. Đây là điều
  kiện đủ; hình rời còn có thể đặt ở nơi không chứa được cả hình chữ nhật.
- Dự báo trộn các khay đã đọc ổn định với khay thử sinh tự động: thanh dài,
  hình chữ nhật, đường chéo và hình tăng trưởng từ các ô kề nhau. Có xét
  những hình không thuộc danh mục cũ. Những mẫu này là giả định để đo độ
  linh hoạt, không phải biết trước kết quả sinh khối của Shopee.
- Giữ kế hoạch khay hiện tại khi bàn sau từng bước khớp dự tính. Dùng
  Accessibility continued strokes để đọc phản hồi trong khi còn giữ khối;
  chỉ thả khi hình hiện ở đích hai khung liên tiếp, rồi kiểm tra bàn/khay.

Không tự mua, hồi sinh, bấm thưởng hoặc mở ván mới. Game vẫn phải ở phía
trước, điện thoại mở khóa. Có thể dừng do hình bị cắt, màn bị che, Android
hủy cử chỉ hoặc bàn sau thả khác dự tính.

## Kiểm chứng và giới hạn

9 kiểm tra lõi Java đạt; Android Lint không có lỗi. Instrumentation trên
S23+ kiểm tra mã Bitmap/HSV thật: 2 fixture bàn và khay đều khớp. Những
kiểm tra này không chứng minh toàn bộ Auto chơi đúng trên mọi ván: vẫn cần
kiểm tra cấp quyền, luồng chụp màn hình và kéo–thả trong game đang chạy.
Chưa có dữ liệu chứng minh bản Android vượt 17k hay hơn bản PC.

Ảnh màn hình cá nhân không được xuất bản. Khi clone repo, instrumentation
dựng ảnh tổng hợp từ dữ liệu ma trận/ô trong `cases.json`; trên workspace
gốc có thể kiểm tra thêm với ảnh thật cục bộ. Các test PC dùng ảnh cần bộ
fixture cục bộ; repo vẫn có mã test nhưng không kèm ảnh phiên cá nhân.

Nhận dạng tự tìm viền xanh và kích thước ô khi có bằng chứng; vùng đọc
khay hiện dựa vào bố cục Shopee đã quan sát. Hình thu nhỏ nối liền không
có đường phân ô rõ có thể không đọc được hoặc cần cải thiện nhận dạng.
Đổi giao diện, hiệu ứng xóa hàng, màu mới và giới hạn hệ thống có thể làm
Auto dừng. Chưa có OCR điểm hoặc giải mã thuật toán sinh khối.

## Build

Mở thư mục `android` bằng Android Studio, dùng JDK 17 và SDK 35:

```sh
./gradlew testDebugUnitTest lintDebug assembleDebug
```

Windows trên workspace này: `powershell -File android/build-local.ps1`.
`tools/setup_android_toolchain.py` tải và kiểm tra SHA256 các công cụ chính
thức; cài thêm SDK platform/build-tools qua sdkmanager. Các công cụ, khóa
ký và đường dẫn máy cục bộ không nằm trong repo. GitHub Actions tạo APK
debug thành artifact ở mỗi lần đẩy main.

Nguồn tham khảo (triển khai Java riêng, không sao chép bộ sinh Shopee):

- [Android MediaProjection](https://developer.android.com/media/grow/media-projection)
- [Android continued strokes](https://developer.android.com/reference/android/accessibilityservice/GestureDescription.StrokeDescription)
- [Exact batch and robustness reference](https://github.com/zacharygoh/block-blast-solver)
- [Blokie geometry heuristics](https://github.com/gary-z/blokie)
