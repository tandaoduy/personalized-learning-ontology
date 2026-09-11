# Hướng dẫn triển khai Docker

## Yêu cầu

- Docker Engine và Docker Compose plugin.
- Một giá trị bí mật cho `SECRET_KEY`.

## Chạy từ image đã đóng gói

Tải artifact deployment từ GitHub Actions, giải nén và nạp image:

```bash
gunzip -c app-image.tar.gz | docker load
```

Tạo file `.env` từ `.env.example`, sau đó đặt `SECRET_KEY` thành chuỗi ngẫu nhiên an toàn và đặt `APP_IMAGE` theo giá trị trong `IMAGE.txt`.

```bash
cp .env.example .env
# chỉnh SECRET_KEY và APP_IMAGE trong .env
docker compose up -d
```

Ứng dụng mặc định lắng nghe tại `127.0.0.1:8000`. Đặt `APP_PORT` trong `.env` nếu cần đổi cổng host.

## Kiểm tra và dừng dịch vụ

```bash
docker compose ps
docker compose logs -f app
docker compose down
```

Không đưa file `.env` chứa `SECRET_KEY` vào Git.
