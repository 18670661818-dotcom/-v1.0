@echo off

call D:\Anaconda\Scripts\activate.bat yolo-v8

cd /d D:\2026\yolo-v8\backend

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause