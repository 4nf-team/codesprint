from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import random
import time

app = FastAPI()

# Разрешаем расширению стучаться на наш локальный сервер
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    # Имитируем время работы нейросети (1 секунда)
    time.sleep(1) 
    
    # Пока что выдаем рандомный результат (True или False)
    is_fake = random.choice([True, False])
    
    # Имитируем ответ от Llama
    if is_fake:
        explanation = "The model detected unnatural blending around the jawline and inconsistent lighting on the subject's face, typical for AI generation."
    else:
        explanation = "No significant artifacts found. The skin texture and lighting appear consistent with organic photography."
        
    return {"is_fake": is_fake, "explanation": explanation}