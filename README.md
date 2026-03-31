# Video Posting Manager

เว็บแอปสำหรับเก็บข้อมูลวิดีโอที่จะนำไปโพสต์ลงแพลตฟอร์มต่าง ๆ พร้อมหน้าแสดงรายการ เพิ่ม แก้ไข และลบข้อมูล โดยเชื่อมกับ PostgreSQL

## เทคโนโลยี

- Flask
- PostgreSQL
- psycopg 3

## วิธีรัน

1. สร้าง virtual environment และติดตั้ง dependencies
2. แก้ค่าฐานข้อมูลใน `.env` หากต้องการ
3. ถ้าจะให้ dropdown ของ `Device / Platform / Account / Workflow` ดึงจาก API ให้ตั้งค่า `REFERENCE_API_BASE_URL`
4. ถ้าจะส่งข้อมูลออกเป็น `Upload Job` ให้ตั้งค่า `UPLOAD_API_BASE_URL` และ `UPLOAD_API_KEY` หากมี
5. รันคำสั่ง:

```powershell
.venv\Scripts\python app.py
```

จากนั้นเปิด `http://127.0.0.1:5000`

## โครงสร้างข้อมูล

แอปจะสร้างตาราง `video_posts` อัตโนมัติถ้ายังไม่มี โดยมีคอลัมน์หลัก:

- `device_id`
- `device_platform_id`
- `account_id`
- `workflow_id`
- `code_product`
- `link_product`
- `title`
- `description`
- `tags` แบบ `TEXT[]`
- `video_url`
- `cover_url`
- `local_video_path`
- `status`

## Docker Auto Start On Ubuntu

โปรเจกต์มีไฟล์ `docker-compose.yml` ที่ตั้ง `restart: unless-stopped` ไว้แล้ว และมี template systemd service ชื่อ `video-posting-manager.service`

วิธีใช้บน Ubuntu:

1. clone โปรเจกต์ไปยัง path จริง เช่น `/opt/webui`
2. แก้ `WorkingDirectory=/opt/webui` ในไฟล์ `video-posting-manager.service` ถ้า path จริงไม่ตรงกัน
3. คัดลอกไฟล์ไปไว้ที่ `/etc/systemd/system/`
4. รันคำสั่ง:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now video-posting-manager.service
```

เช็กสถานะ:

```bash
sudo systemctl status video-posting-manager.service
sudo docker compose ps
```
