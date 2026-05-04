# Hướng dẫn cài đặt lệnh tắt `reclip` 🚀

Tài liệu này hướng dẫn bạn cách thiết lập để chỉ cần gõ duy nhất một từ `reclip` trong Terminal là dự án sẽ tự động khởi động và mở trình duyệt.

## 1. Thiết lập Alias (Dành cho macOS)

Mở Terminal và chạy lệnh sau (đã bao gồm đường dẫn chính xác đến thư mục dự án của bạn):

```bash
echo 'alias reclip="cd \"/Users/tuananh/Tuan Anh/Code/reclip\" && ./reclip.sh"' >> ~/.zshrc
```

## 2. Kích hoạt thay đổi

Để máy tính nhận diện lệnh mới ngay lập tức mà không cần khởi động lại, hãy chạy:

```bash
source ~/.zshrc
```

*Lưu ý: Nếu bạn dùng các tab Terminal cũ đã mở từ trước, bạn cần chạy lệnh `source` này ở mỗi tab đó, hoặc đơn giản là tắt Terminal đi mở lại.*

## 3. Cách sử dụng

Từ giờ trở đi, bất kể bạn đang ở thư mục nào, chỉ cần gõ:

```bash
reclip
```

**Hệ thống sẽ tự động thực hiện:**
1. Di chuyển vào thư mục ReClip.
2. Kích hoạt môi trường ảo (venv).
3. Khởi động Flask Server.
4. **Tự động mở trình duyệt Chrome/Safari** dẫn trực tiếp đến ứng dụng.

---

## 💡 Mẹo nhỏ

### Cách xóa lệnh tắt
Nếu sau này bạn không muốn dùng lệnh này nữa, hãy mở file `~/.zshrc` (bằng lệnh `nano ~/.zshrc`), tìm dòng có chữ `alias reclip` và xóa nó đi, sau đó lưu lại.

### Đảm bảo quyền thực thi
Nếu gõ `reclip` mà báo lỗi "Permission denied", hãy chạy lệnh này một lần:
```bash
chmod +x "/Users/tuananh/Tuan Anh/Code/reclip/reclip.sh"
```
