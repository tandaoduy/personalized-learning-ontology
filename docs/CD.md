# Chuẩn bị triển khai khi chưa có server

Hiện có pipeline CI và đóng gói liên tục (Continuous Delivery): tests → Docker build → chạy container production → kiểm tra HTTP và ontology → lưu gói triển khai. Chưa có bước tự triển khai lên server (Continuous Deployment).

Workflow vẫn tên CI. Job `package` chạy sau `build-and-test`, kể cả pull request để phát hiện lỗi Dockerfile. Chỉ nhánh `main` xuất artifact `deployment-<commit SHA>`, lưu 14 ngày. Không cần VPS, registry hay secret GitHub. Image được build trên Ubuntu x86-64; server dùng gói này cần Linux x86-64 và Docker Compose v2.

Dockerfile build UI bằng Node 22, chạy Flask bằng Python 3.14 và Gunicorn, dưới UID 10001. Một worker đồng bộ được dùng vì dữ liệu hiện lưu bằng JSON, chưa phù hợp chạy nhiều replica cùng ghi dữ liệu.

## Kích hoạt trên GitHub

Commit và push các file cấu hình. Vào Actions → CI → lần chạy mới nhất. Chỉ tải gói trong Artifacts khi cả hai job đều xanh. Gói gồm image đã kiểm tra, Compose, mẫu biến môi trường, tên image và checksum. Nên tải giữ bản muốn triển khai trước khi artifact hết hạn.

## Chạy thử trên máy có Docker

Tại gốc repository, trong PowerShell:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Điền giá trị vừa sinh vào `SECRET_KEY` trong `.env`, giữ nguyên khóa này qua các lần cập nhật. Không commit `.env`. Sau đó:

```powershell
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
Invoke-RestMethod http://localhost:8000/api/health
docker compose logs --tail 100 app
```

Đây là cấu hình production: cookie phiên yêu cầu HTTPS. HTTP localhost chỉ dùng kiểm tra health; để kiểm tra đăng nhập production và mở ứng dụng cho người dùng, cần reverse proxy HTTPS. Có thể tiếp tục chạy `python run_app.py` để phát triển giao diện trên localhost.

## Dùng gói đã build khi có VPS

Cài Docker Engine và Compose v2 trên Linux x86-64. Tải artifact từ GitHub, giải nén và chuyển các file vào một thư mục triển khai cố định trên VPS. Các lệnh sau dùng Bash tại thư mục đó:

```bash
sha256sum -c SHA256SUMS
docker load -i app-image.tar.gz
cp .env.example .env
openssl rand -hex 32
```

Sửa `.env`: điền `SECRET_KEY`, đặt `APP_IMAGE` đúng giá trị trong `IMAGE.txt`. Sau đó:

```bash
docker compose up -d --no-build --wait --wait-timeout 120
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
```

Compose chỉ mở cổng trên loopback. Bước kết nối hosting sau này cần cấu hình domain và reverse proxy HTTPS tới `127.0.0.1:8000`.

## Dữ liệu và tài khoản

Image không chứa thư mục `data/` của repository hoặc tài khoản demo. Volume `app-data` gắn tại `/app/data` lưu hồ sơ, tài khoản và phản hồi độc lập với image. Lần chạy đầu volume chưa có hồ sơ/tài khoản; health thành công chỉ xác nhận ứng dụng và ontology sẵn sàng, không xác nhận dữ liệu học vụ đã được nhập.

Trước khi sử dụng thật, chuẩn bị bộ JSON/CSV và tài khoản đã được kiểm tra. Khi khởi tạo lần đầu, có thể nhập thư mục dữ liệu trên VPS bằng các lệnh Bash dưới đây (thay đường dẫn mẫu):

```bash
docker compose stop app
docker compose cp /path/to/approved-data/. app:/app/data/
docker compose run --rm --no-deps --user root app chown -R 10001:10001 /app/data
docker compose up -d --no-build --wait --wait-timeout 120
```

Sao lưu dữ liệu trước khi thay đổi. Không tự chép dữ liệu demo đè lên volume đang sử dụng. Giữ nguyên thư mục triển khai/tên Compose project để tiếp tục dùng đúng volume. `docker compose down` giữ volume; không dùng `docker compose down -v` khi cần giữ dữ liệu.

## Cập nhật và quay lại bản trước

Giữ image cũ và ghi lại `APP_IMAGE` trước khi cập nhật. Nạp image mới bằng `docker load`, đổi `APP_IMAGE` trong `.env`, rồi chạy `docker compose up -d --no-build --wait --wait-timeout 120`.

Nếu bản mới không đạt health, đổi `APP_IMAGE` về tag cũ và chạy lại lệnh trên. Cách này quay lại mã ứng dụng; không hoàn tác dữ liệu đã ghi. Bản thay đổi định dạng dữ liệu cần kế hoạch migration/khôi phục riêng.

## Bước bổ sung khi chọn được hosting

Thêm job deploy chỉ chạy trên `main`, phụ thuộc job `package`, dùng chính image đã kiểm tra. Khi đó mới cấu hình kết nối server hoặc API hosting bằng GitHub Secrets, HTTPS, backup và kiểm tra sau deploy. Hiện không có job deploy giả hay secret bắt buộc khiến workflow bị lỗi khi chưa có server.

Tham khảo: [Docker multi-stage build](https://docs.docker.com/build/building/multi-stage/), [GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts), [Compose environment variables](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
