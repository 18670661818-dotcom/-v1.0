@echo off
echo Starting Kitchen AI Inference Service...
cd /d d:\2026\kitchen_ai_system\backend
python -m services.inference_service
pause
