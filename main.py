"""
SDXL Image Forge — FastAPI Backend
Corre en HF Spaces (ZeroGPU) o Google Colab + ngrok.
El modelo se carga UNA VEZ al arrancar y queda en memoria GPU.
"""

import os
import io
import base64
import logging
import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from diffusers import DiffusionPipeline

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Model config
# ─────────────────────────────────────────────
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"  # T4 de Colab aguanta con fp16
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE    = torch.float16 if DEVICE == "cuda" else torch.float32

# Pipeline global — se carga una sola vez
pipe = None


# ─────────────────────────────────────────────
# Lifespan: carga el modelo al arrancar
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
    logger.info(f"⚙️  Cargando SDXL en {DEVICE} ({DTYPE})...")
    pipe = DiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        use_safetensors=True,
        variant="fp16" if DEVICE == "cuda" else None,
    )
    pipe = pipe.to(DEVICE)

    if DEVICE == "cuda":
        pipe.enable_attention_slicing()
        pipe.enable_vae_slicing()   # Libera VRAM extra — clave en 3050/4GB

    logger.info("✅ Modelo cargado y listo.")
    yield
    # Cleanup al apagar
    del pipe
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    logger.info("🛑 Modelo liberado.")


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="SDXL Image Forge",
    description="Generación fotorrealista con Stable Diffusion XL corriendo en GPU propia.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)
    negative_prompt: Optional[str] = Field(
        default="cartoon, anime, low quality, blurry, watermark, text, logo, nsfw"
    )
    # Turbo: guidance_scale=0 y 1-4 pasos es lo óptimo
    guidance_scale: float = Field(default=7.5, ge=0.0, le=20.0)
    num_inference_steps: int = Field(default=30, ge=1, le=50)
    seed: Optional[int] = Field(default=None)
    width: int = Field(default=1024, ge=512, le=1024)
    height: int = Field(default=1024, ge=512, le=1024)

class GenerateResponse(BaseModel):
    image_base64: str
    prompt_used: str
    parameters: dict


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": pipe is not None,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate_image(req: GenerateRequest):
    if pipe is None:
        raise HTTPException(
            status_code=503,
            detail="El modelo aún no ha terminado de cargar. Espera unos segundos."
        )

    generator = None
    if req.seed is not None:
        generator = torch.Generator(device=DEVICE).manual_seed(req.seed)

    logger.info(f"🎨 Generando: '{req.prompt[:60]}' | steps={req.num_inference_steps} | cfg={req.guidance_scale}")

    try:
        with torch.inference_mode():
            result = pipe(
                prompt=req.prompt,
                negative_prompt=req.negative_prompt,
                guidance_scale=req.guidance_scale,
                num_inference_steps=req.num_inference_steps,
                width=req.width,
                height=req.height,
                generator=generator,
            )

        image = result.images[0]

        # PIL Image → bytes → base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        image_b64 = base64.b64encode(buffer.read()).decode("utf-8")

        logger.info("✅ Imagen generada correctamente.")

        return GenerateResponse(
            image_base64=image_b64,
            prompt_used=req.prompt,
            parameters={
                "guidance_scale": req.guidance_scale,
                "num_inference_steps": req.num_inference_steps,
                "negative_prompt": req.negative_prompt,
                "seed": req.seed,
                "width": req.width,
                "height": req.height,
                "device": DEVICE,
            },
        )

    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        raise HTTPException(
            status_code=500,
            detail="GPU sin memoria. Reduce num_inference_steps o resolución e intenta de nuevo."
        )
    except Exception as e:
        logger.exception("Error durante la generación")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/presets")
async def get_presets():
    return {
        "presets": [
            {
                "style": "Fantasía Oscura",
                "prompt": "burned medieval knight in full plate armor, charred black metal armor cracked with glowing embers, lava-like fissures emitting orange and red light, tattered cape disintegrating into ash, apocalyptic yellow sky, ruined gothic castle, cinematic dark fantasy atmosphere, photorealistic, masterpiece",
                "negative_prompt": "cartoon, anime, low poly, plastic armor, bright colors, blurry, watermark"
            },
            {
                "style": "Ciencia Ficción",
                "prompt": "futuristic cyberpunk city at night, neon lights reflecting on wet streets, flying cars, holographic advertisements, dense fog, ultra detailed, cinematic lighting, photorealistic, 8k",
                "negative_prompt": "cartoon, anime, low quality, blurry, watermark, daylight"
            },
            {
                "style": "Naturaleza Épica",
                "prompt": "majestic snow-capped mountain at golden hour, dramatic clouds, crystal clear lake reflection, ancient pine forest, volumetric light rays, ultra realistic landscape photography, sharp focus, masterpiece",
                "negative_prompt": "cartoon, people, buildings, text, watermark, blurry"
            },
            {
                "style": "Retrato",
                "prompt": "cinematic portrait of a wise old explorer, weathered face with deep wrinkles, piercing blue eyes, dramatic side lighting, shallow depth of field, film grain, Kodak Portra 400, photorealistic",
                "negative_prompt": "cartoon, anime, painting, illustration, low quality, watermark"
            },
        ]
    }
