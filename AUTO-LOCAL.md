# Auto local: điều khiển tự thích nghi

Bản 15 (10/10/2026): ưu tiên vùng trống dùng được, giảm cạnh phân mảnh, và giữ trọn kế hoạch của khay hiện tại khi bàn/khối thực tế khớp dự tính. Đổi bàn hoặc đổi khay sẽ hủy phần kế hoạch cũ. Việc đọc HTML nhiều lần không được làm mất kế hoạch còn lại.

Nguồn tham khảo đã đọc: [Blokie](https://github.com/gary-z/blokie) về lập kế hoạch cả ba khối và giữ bàn gọn; [bộ kiểm tra khả thi theo khay](https://github.com/zacharygoh/block-blast-solver/blob/main/packages/core/src/solver.ts) về tìm kiếm có nhớ trạng thái. Đây là triển khai Python riêng, dùng quy luật 8×8 hiện tại; không lấy quy luật xóa vùng 3×3 của Woodoku.

Bộ kiểm tra khả thi có ba kết quả: tìm được đường đặt đủ, duyệt hết và không có đường, hoặc chưa biết vì hết ngân sách 4.000 nút. Chỉ áp dụng đường cứu khi nó dùng đúng các khối đang nhìn thấy và có thể phát lại hợp lệ. Mô hình khay giả định giữ tối đa 24 khay mới nhất, bắt đầu tính trọng số gần đây sau 8 khay đã xác minh; khối mới vẫn được bổ sung từ hình thực tế.

Kiểm chứng cuối: 77 kiểm thử; sáu hạt độc lập 2500–2505 cho mỗi phân phối, tối đa 180 nước, cùng độ rộng 40 và ngân sách 0,5 giây. So với bản 14: điểm mô phỏng trung bình tăng 8,9% với danh mục rộng và 5,1% khi nhiều khối lớn; giảm 2,5% với nhóm khối quen. Thời gian tìm kiếm mỗi nước giảm khoảng 32–39% nhờ giữ kế hoạch cả khay. Điểm này là đơn vị của bộ mô phỏng, không phải điểm Shopee; chưa có kiểm chứng rằng điện thoại sẽ vượt 17k.

Kết quả: `artifacts/spatial-holdout.json` (bản cũ) và `artifacts/committed-holdout.json` (bản chọn). Tái lập bản chọn: `.venv\Scripts\python.exe tools/benchmark_survival.py --seeds 6 --start 2500 --moves 180 --width 40 --budget .5 --variants committed --pools observed,broad,large_stress --prior artifacts/lookahead-profile-99.json --output artifacts/committed-holdout.json`. Các thử nghiệm tăng phạt rủi ro và đổi trọng số tự động không cải thiện ổn định, nên không bật trong Auto.

Bản 14: đọc trọn từng phần ba của khay, nhận thanh ngang 5 ô mà vùng đọc cũ cắt mất hai đầu. Khối chạm mép vùng đọc bị từ chối để tránh lập kế hoạch từ hình thiếu ô. Kiểm tra hồi quy bằng ảnh điện thoại tại 15.193 điểm, cả ảnh gốc và ảnh qua nén luồng LIVE; không cần khai báo mẫu riêng cho thanh mới.

Bản này thay bộ căn theo độ lệch cố định bằng vòng phản hồi hình ảnh. Chạy hoàn toàn trên PC, không gọi mô hình AI hay dịch vụ cloud.

## Mỗi lần kéo

1. Đọc bàn và khay ổn định. Tính các vị trí hợp lệ bằng đúng tập ô của khối, kể cả khối chéo và ô rời. Chỉ sử dụng các khối đang thấy.
2. Chọn ô có gạch thật để nhấn. Kéo gần mục tiêu.
3. Theo dõi hình khối theo viền màu của từng ô. Các ô đã có trên bàn được đối chiếu ảnh trước kéo; các ô trống bên trong L/T/Z không bị hiểu là phần bắt buộc phải trống của bàn. Viền giúp tránh biểu tượng đá quý che giữa ô.
4. Sau mỗi lệnh chỉnh, chờ khung hình mới. Đo chuyển động con trỏ và chuyển động khối; cập nhật ma trận đáp ứng 2D bằng phép cập nhật secant. Tính bước chỉnh từ sai số đang thấy, giới hạn 1.5 ô mỗi bước. Không coi thông số của khối/cấp trước là bằng chứng vị trí hiện tại đã đúng.
5. Chỉ nhả khi bóng xám hoặc hiệu ứng xóa hàng/cột kèm dấu ô nhận đúng mục tiêu được xác nhận hai lần. Hình khối nổi chỉ dùng để điều chỉnh, không cho phép tự nhả khi thiếu tín hiệu game.
6. Đối chiếu bàn sau nhả với bàn dự tính. Nếu đã thả lệch, dừng Auto và lưu chẩn đoán; không tự tiếp tục trên bàn sai. Nếu khối chưa đặt được, trả về khay và tự căn lại.
7. Sau nhiều lỗi căn: bỏ hiệu chuẩn cũ, tăng thời gian chờ (tối đa 10 giây), đọc lại bàn và tự đo lại. Auto vẫn bật. Màn thua và thao tác tay vẫn dừng Auto.

## Kiểm chứng

164 tests đạt. Có 1.000 trường hợp độ lệch/ma trận đáp ứng; 30 mẫu hình thử cả có/không biểu tượng giữa ô; 12 lượt kéo có ô nhận đúng và 12 lượt bị chặn khi không có ô nhận; kiểm tra thả lệch gây dừng thay vì tăng số nước thành công.

Các thử nghiệm mới không phát nước thử vào điện thoại thật. Mô phỏng không chứng minh mọi tình huống trên máy thật đều hội tụ.

## Phạm vi

Hiện hiệu chỉnh cho S23+ 1080×2340, bàn 8×8 và vùng khay hiện tại. Bộ đọc khối giới hạn hình trong lưới tối đa 5×5 và phải nhìn trọn khối trong vùng khay. Đổi bố cục, kích thước bàn, quy luật game hoặc xuất hiện khối bị cắt/che vẫn có thể cần cập nhật nhận diện. Không cam kết thắng mọi cấp; chưa tối ưu riêng mục tiêu đá quý bằng OCR.

Điều khiển: drag_servo.py. Theo dõi: vision/piece_tracker.py. Điều phối: autopilot.py.

Tham khảo nguyên lý phản hồi thị giác: Chaumette & Hutchinson, Visual Servo Control, Part I (2006), https://web.mit.edu/amcp/OldFiles/drg/Chaumette_Part_I.pdf . Bộ điều khiển 2D, ràng buộc và ngưỡng tại đây là triển khai riêng cho ứng dụng, không phải chứng minh hội tụ của hệ robot trong bài báo.


Lịch sử dự định và kết quả: artifacts/auto-moves.jsonl (planned/verified/mismatch), gồm bàn trước, ô dự định và bàn thực tế.

Bản auto-local-5: nắm ô có gạch gần tâm nhất; khóa mục tiêu cho bàn/khay không đổi; không đổi sang phương án thứ hai khi căn lỗi. Ảnh ngay trước nhả lưu ở artifacts/auto-before-release.png, cùng sự kiện release_authorized và tọa độ con trỏ trong auto-moves.jsonl. Đây là dữ liệu chẩn đoán, chưa chứng minh lỗi lệch cột trên điện thoại thật đã được loại bỏ.

Bản auto-local-7: HTML giữ ô vàng và chuỗi nước đang thực hiện khi Auto kéo; hai bàn đối chiếu sau thả đánh dấu ô khác nhau. `execution` được gắn với mã bàn trước lần kéo, tách khỏi gợi ý của bàn mới; `last_check` lưu kết quả lần thả gần nhất. Lượt thử thật bắt được khối một ô: ô xám báo hàng 2/cột 5 nhưng thực tế vào hàng 1/cột 6. Vì vậy, trước khi nhả phải xác nhận đồng thời vị trí khối gần mục tiêu (sai số dưới 0,22 ô mỗi trục) và ô nhận, lặp lại trên khung mới. Không dùng độ lệch của khối để bỏ qua điều kiện này. Nếu bằng chứng mâu thuẫn thì căn lại hoặc trả về khay; chưa cam kết mọi lượt đều đặt được.

Khối bị cắt ở mép ảnh được dịch vào trong để nhìn trọn rồi căn lại. Hiệu ứng viền hàng/cột sáng được tách khỏi các mảnh ô nhận; các mảnh nhỏ được cộng đủ bằng chứng, nhưng vùng ô nhận lớn nằm ngoài mục tiêu vẫn bị từ chối. Màn tĩnh có thể không sinh khung video mới: trước lần xác nhận thứ hai, Auto dịch con trỏ 1 pixel của luồng 540 px rồi đọc lại vị trí và ô nhận. Không cho nhả bằng ảnh cũ. Các ảnh hồi quy thực tế nằm trong captures/auto-gray-sprite-conflict.png, auto-clipped-z.png, auto-clear-column-border.png và auto-clear-fragments.png.

Bản auto-local-8 giữ trạng thái settling sau hủy kéo, chờ bàn và khay khớp trạng thái trước lần kéo 3 lần liên tiếp mới cho tính tiếp. Hình khối đang bay về khay không được tính là khối đã đặt. Nếu hết thời gian chờ mà chưa khớp, Auto dừng và lưu abort_mismatch, không tính tiếp từ bàn tạm.
# Giới hạn vùng căn khối (bản 9)

Sửa trong lượt chơi tiếp: lấy khối cách mép bàn một ô trước khi căn mục tiêu, tránh mất dấu do độ lệch nâng khối chưa được đo. Khi dự đoán xóa hàng/cột, phép so sánh trước–sau bỏ qua đổi màu của các ô đã có trên chính các đường đó; các ô trống vẫn giữ nguyên để nhận ra khối mới hoặc khối đặt lệch. Vẫn yêu cầu dấu ướm và vị trí khối khớp trước khi nhả. Sự kiện `drag_failed` ghi loại lỗi, nội dung và tọa độ điểm chạm trong `artifacts/auto-moves.jsonl`.

Nếu dấu ướm bị hiệu ứng che mất, chỉ dùng các hàng/cột sáng thay thế khi bộ đường xóa đó xác định duy nhất một nước hợp lệ của khối hiện tại, đồng thời vị trí khối vẫn phải khớp trên ảnh mới. Khối che kín dấu ướm được dịch 0,14 ô vào trong để lộ hai cạnh, không vượt giới hạn căn khối.

`play_until_loss.py` theo dõi ván hiện tại, sao lưu ảnh lỗi và log vào `artifacts/play-until-loss-log`, kết thúc khi API báo `game_over`. Không vào ván mới và không dùng trợ giúp. Nút Dừng Auto được tôn trọng. Với hai lỗi xác minh có thể phục hồi, bộ theo dõi chỉ bật lại sau ba lần đọc bàn/khay ổn định và để Auto tính từ bàn thực tế. Khi kết thúc, `summary.json` ghi kết quả và `final-screen.png` giữ màn cuối. Đây là tiến trình local; không gọi model/API AI.

Các bước chỉnh và yêu cầu khung hình mới được giới hạn theo toàn bộ khối trong bàn cờ, dựa trên vị trí khối quan sát được và mô hình phản hồi chuyển động. Giới hạn áp dụng cho khối, không phải vị trí ngón tay: game nâng khối lên trên ngón tay. Đoạn lấy từ khay và trả về khay khi hủy vẫn đi ngoài bàn.

Không nhìn rõ toàn bộ khối thì hủy và trả khay; không dò mù ra mép màn hình. Trước khi nhả vẫn cần khối nằm trong bàn và dấu ướm đúng mục tiêu trên khung hình mới. Giới hạn dự đoán không bảo đảm tuyệt đối chuyển động vật lý nếu mô hình hoặc nhận dạng sai; cần tiếp tục xác minh trên điện thoại.

## Tối ưu điểm cổ điển — bản 10

Auto và gợi ý HTML dùng cùng `CLASSIC_WEIGHTS`: cleared=20, empty=1,
mobility=0.2, holes=6, fragmentation=3, coverage=45, options=12.
Tìm kiếm vẫn xét thứ tự và vị trí của toàn bộ khay hiện tại, ưu tiên kế hoạch
đặt được nhiều khối hơn. Sau mỗi nước đã xác minh, tính lại từ bàn điện thoại.

Ngoài bốn dạng đo độ linh hoạt cũ, `solver/shape_prior.py` đếm vị trí hợp lệ
cho 44 dạng giả định, gồm thanh dài tới 5 ô, vuông 3×3, chữ nhật 2×3,
L/T/Z/cross và đường chéo. Đây là phân bố giả định đều để giữ chỗ cho khối
khó, không phải danh sách đầy đủ của Shopee hoặc khả năng biết trước khay mới.
Tỉ lệ dạng còn đặt được nhận trọng số riêng; số chỗ đặt dùng log(1+n) để
không đánh đổi chỗ cuối của khối khó lấy nhiều chỗ của khối dễ. Phép giao
bit đếm các vị trí nhanh; kết quả được lưu cache. Dạng khối hiện tại vẫn
được tính theo tập ô thực tế, không bị giới hạn bởi 44 dạng giả định này.

Đánh giá trên các chuỗi cùng seed, tính lại sau từng nước:

| Bộ kiểm tra | Cũ: nước / hàng-cột xóa | Bản 10: nước / hàng-cột xóa |
| --- | --- | --- |
| 8 chuỗi, 21 dạng từng thấy, tối đa 180 nước | 73.50 / 33.00 | 107.00 / 49.38 |
| 8 chuỗi, 44 dạng giả định, tối đa 180 nước | 132.12 / 62.62 | 131.25 / 62.12 |
| 6 chuỗi tăng tần suất khối lớn, tối đa 150 nước | 26.00 / 13.00 | 28.83 / 15.33 |

Kiểm tra dùng beam width 40 và ngân sách 0.18–0.20 giây. Đây là mẫu nhỏ,
có ván chạm giới hạn nước, không chứng minh tối ưu hoặc chắc chắn tăng
điểm từng ván. Điểm mô phỏng dùng luật tạm của engine, không quy đổi sang
điểm Shopee. Kết quả trên điện thoại với ngân sách khác có thể khác.
Mức giữ chỗ mạnh hơn (90/20) đã được thử và không được chọn vì kết quả
tổng thể thấp hơn mức 45/12 trên các bộ kiểm tra này.

Lệnh tái lập: `.venv\Scripts\python.exe tools\benchmark_survival.py --seeds 8 --start 700 --moves 180 --width 40 --budget .18 --output artifacts/survival-holdout.json`.
Stress: thêm `--seeds 6 --start 900 --moves 150 --budget .2 --variants baseline,reserve --pools large_stress --output artifacts/survival-large-stress.json`.
Log so sánh: `artifacts/survival-tuning.json`, `survival-holdout.json`,
`survival-large-stress.json`.

Màn thua cổ điển được nhận diện bằng hai nhãn cố định, bỏ qua số điểm
thay đổi. Kiểm tra màn thua trước màn thắng vì hai màn dùng cùng hình gà
và nút vàng. Auto dừng khi thua, không tự bấm Tham gia lại.

## Căn khối ở mép — bản 11

Lấy khối vào giữa vùng bàn trước khi căn. Độ lệch điểm chạm được đo lại
từ hình khối nổi, không lấy từ bóng xám đã làm tròn theo ô. Bộ điều khiển
S23+ học độ nhạy từng trục riêng bằng trung vị năm phép đo đủ lớn; ảnh
trễ không được dùng để suy ra liên kết chéo X/Y. Các bước căn giữ dự
phòng hệ số 2.5 đối với khoảng cách tới mép, cả trên mô hình lẫn lệnh
điểm chạm trực tiếp. Kiểm tra vị trí khối trên ảnh mới vẫn bắt buộc.
Không thấy đủ hình màu thì trả khay, không dùng mẫu ảnh giống một phần
để tiếp tục căn. Một ảnh chỉ được theo dõi một lần trong mỗi bước.

`drag_observed` ghi điểm chạm, gốc hình khối, confidence, sequence và
`inside`. Lượt thử đầu đã thả đúng nhưng log bắt được ba ảnh vượt mép
10–13 px; xem `artifacts/boundary-fix-trial-v1.json`. Sau sửa mô hình
theo từng trục, lượt thử thứ hai thả đúng, cả bảy vị trí khối quan sát
được đều trong bàn; xem `artifacts/boundary-fix-trial.json`. Auto đã
dừng sau từng nước thử. Kiểm chứng hữu hạn này không bảo đảm tuyệt đối
mọi chuyển động chưa quan sát hoặc một gain thật vượt giới hạn dự phòng.

## Ván 16.668 điểm — bản 12

`artifacts/loss-16668/analysis.json` lưu phân tích 40 nước xác minh khớp,
4 lần căn bị hủy và 5 vị trí quan sát vượt mép trong 288 ảnh đo. Các lần
vượt mép là vấn đề còn tồn tại của điều khiển, không được tính là đã hết
lỗi sau một lượt thử thành công. Nước cuối khớp bàn dự tính; cả 10 nước
hợp lệ tại bàn trước đó đều để lại khối 3×3 không đặt được. Duyệt đầy đủ
đầu khay cuối cũng không tìm được cách đặt hết cả ba khối; cần giữ chỗ
từ khay trước, không thể sửa bằng cách đổi nước cuối.

Thêm mẫu chữ THUA CUỘC cổ điển cùng kiểm tra nút Tham gia lại. Auto
cũng dừng khi bàn/khay đã xác minh không còn bất kỳ nước hợp lệ nào,
không đợi mãi ảnh hộp thoại. Mẫu game-over 17.760 là màn đạt kỷ lục;
màn thua thường dùng hình/chữ khác. Ảnh người dùng gửi được lưu thành
`reported-loss.png`; `current-phone-readonly.png` là ảnh đọc sau đó,
khi điện thoại đã ở ván khác, không phải ảnh kết thúc ván 16.668.

## Dự đoán rủi ro khay tương lai — bản 13

`solver/stochastic.py` xét tối đa 12 bàn kết thúc khay hiện tại khác nhau,
không dành các phương án chỉ cho những thứ tự đặt khác nhau nhưng ra cùng
bàn. Với mỗi bàn, thử các chuỗi khay giả định bằng tìm kiếm nhỏ theo đúng
luật đặt/xóa hàng-cột, kể cả khả năng đặt khối này để mở chỗ cho khối kia.
Đánh giá kết hợp giá trị bàn hiện tại, số khối tương lai đặt được trung
bình, số đường xóa và kịch bản sống được ít nhất. Chỉ khay hiện tại đặt
hết mới được thay bằng khay giả định. Không đưa ID hay ô của khối giả định
vào lệnh kéo thật.

Tần suất lấy từ 99 lần đổi khay đã xác minh (297 khối, 30 dạng), trộn
50% tần suất thực tế, 30% phân bố rộng và 20% khối lớn để tránh chỉ học
các dạng dễ đã gặp. Sau mỗi đổi khay thật đã xác minh, cập nhật bộ đếm
và lưu `config/shape-prior.json`. Cả ba chế độ dùng chung mô hình; cache
dự đoán được vô hiệu hóa theo phiên bản mô hình. Các lần căn lại/chụp
lặp không được tính là khay mới. Có thể dựng lại dữ liệu từ log bằng
`tools/build_shape_prior.py`.

Nhanh: tối đa 2 kịch bản, nhìn 1 khay tiếp theo. Cân bằng: 4 kịch bản,
nhìn 2 khay. Kỹ: 8 kịch bản, nhìn 2 khay. Giới hạn thời gian vẫn là
180/850/3000 ms; hết ngân sách có thể xét ít kịch bản hơn. Các phương án
luôn dùng cùng bộ mẫu: vòng chưa xét hết tất cả phương án bị bỏ, không
để ứng viên cuối chịu bộ mẫu khác ứng viên đầu. Tìm kiếm dự đoán là xấp
xỉ, không chứng minh tối ưu hoặc biết trước RNG của game.

HTML hiện “qua X/Y kịch bản N khay giả định”. Đây là kết quả trên các
mẫu đã xét, không phải xác suất thắng đã được hiệu chuẩn. Ô vàng vẫn
chỉ mô tả nước thật đang thực hiện, và điều kiện xác minh trước/sau nhả
được giữ nguyên. Bản này không giải quyết riêng những lần vượt mép còn
ghi nhận ở ván 16.668.

So sánh giữ cố định dữ liệu 99 khay, mỗi bộ 6 chuỗi cùng seed 1500–1505,
giới hạn 150 nước, beam width 40, ngân sách 400 ms, dự đoán 4 kịch bản
với 2 khay:

| Bộ thử | Bản 12: nước / đường xóa | Bản 13: nước / đường xóa |
| --- | --- | --- |
| Dạng đã gặp | 72.67 / 32.33 | 122.83 / 59.33 |
| Bộ 44 dạng rộng | 120.50 / 58.33 | 143.17 / 70.83 |
| Tăng tần suất khối lớn | 35.67 / 19.17 | 51.17 / 29.17 |

Đây là mô phỏng nhỏ, có ván chạm giới hạn 150 nước; điểm engine không
phải điểm Shopee. Chưa có ván điện thoại kiểm chứng mức tăng điểm này.
Dữ liệu và mẫu mô hình: `artifacts/lookahead-validation.json`,
`artifacts/lookahead-profile-99.json`. Tái lập:
`.venv\Scripts\python.exe tools\benchmark_survival.py --seeds 6 --start 1500 --moves 150 --width 40 --budget .4 --variants reserve,lookahead --pools observed,broad,large_stress --prior artifacts/lookahead-profile-99.json --output artifacts/lookahead-validation.json`.

# Bản 16: khay có tương quan (10/10/2026)

Mô hình lưu tối đa 48 bộ ba từ các lần đổi khay đã xác minh. Dự báo trộn
50% khay trong 24 lần gần nhất với 50% mẫu rộng, để giữ những tổ hợp khó
như hai khối 3×3 cùng xuất hiện mà vẫn xét hình chưa gặp. Đây là mô hình
thực nghiệm, không phải đã giải mã bộ sinh khối của Shopee.

Chế độ Kỹ xét tối đa 16 kịch bản, mỗi kịch bản 3 khay; giới hạn tính vẫn
3 giây và chỉ những vòng so sánh hoàn chỉnh được dùng để xếp hạng.
Chưa có OCR điểm: không tự chuyển chính xác ở 12k. Có thể chạy Kỹ từ đầu.
53 kiểm tra solver, tương quan khay và thao tác đã qua; chưa có kiểm chứng
thống kê rằng bản 16 tăng điểm trên điện thoại.

# Bản 17: thanh dọc 5 ô (10/10/2026)

Mở rộng mỗi vùng đọc khay từ 240 lên 325 pixel cao để bao trọn thanh
dọc 5 ô nhô ra ngoài viền khay. Ngưỡng sáng 150 loại viền xanh tối;
vẫn từ chối hình chạm mép vùng đọc để tránh nhận thiếu ô.
Fixture thật tại `captures/new-piece-vertical-five.png` được kiểm tra cả
ảnh gốc và JPEG 78/95: A/C có 5 ô dọc, B có 3 ô ngang. 53 kiểm tra
nhận dạng, tương quan khay và thao tác đã qua.

# Bản 18: hình ngoài danh mục (10/10/2026)

Nhận dạng hỗ trợ mẫu ô tùy ý trong giới hạn bàn 8×8, không cần tên hình
trong danh mục. Khi có các thành phần ô nhỏ, đủ rõ và nhất quán, vùng đọc
tự ước lượng pitch nhỏ hơn 58 để đọc hình được game thu nhỏ. Vẫn từ chối
khối bị cắt, quá lớn hoặc các ô không chắc chắn. Không bảo đảm đọc được
mọi kiểu đồ họa/khối nối liền bị thu nhỏ; cần bằng chứng kích thước ô.

Hình mới đọc được bổ sung ngay vào hỗ trợ lấy mẫu tương lai, không tăng
tần suất lịch sử cho đến khi xác minh đổi khay. 80 kiểm tra đạt, gồm ảnh
thật, thanh 8 ô, hình rời và hình chưa có tên ở pitch 24/32/40.
Thay đổi này không giải mã bộ sinh khối, không dự đoán chính xác hình
chưa xuất hiện và chưa chứng minh nâng điểm. Chiến lược hiện có vẫn đánh
giá khoảng trống, độ phân mảnh và các khay giả định.

