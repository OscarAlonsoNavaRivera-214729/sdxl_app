# 🔥 SDXL Image Forge

Generador de imágenes fotorrealistas con **Stable Diffusion XL** corriendo en GPU propia.  
Backend **FastAPI** · Deploy en **Hugging Face Spaces** (GPU gratis).

---

## Estructura del proyecto

```
sdxl-app/
├── main.py            ← FastAPI + SDXL (modelo corre aquí)
├── requirements.txt   ← Dependencias Python
├── README.md          ← Este archivo (también es la card de HF Spaces)
└── static/
    └── index.html     ← Frontend completo
```

---

## ─── PASO A PASO: Deploy en Hugging Face Spaces ───

### PASO 1 — Crear cuenta en Hugging Face
1. Ve a https://huggingface.co/join
2. Crea tu cuenta gratis

### PASO 2 — Aceptar términos del modelo SDXL
1. Ve a https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
2. Haz clic en **"Access repository"** y acepta los términos
   *(sin esto el modelo no se puede descargar)*

### PASO 3 — Crear un nuevo Space
1. Ve a https://huggingface.co/new-space
2. Llena los campos:
   - **Space name**: `sdxl-image-forge` (o el nombre que quieras)
   - **License**: MIT
   - **SDK**: selecciona **Docker** ← importante
   - **Visibility**: Public
3. Haz clic en **Create Space**

### PASO 4 — Crear token de HF (para que el Space descargue el modelo)
1. Ve a https://huggingface.co/settings/tokens
2. Clic en **New token**
3. Tipo: **Write** (necesario para subir archivos al Space)
4. Nombre: `sdxl-deploy`
5. Copia el token `hf_xxxxxxxxxxxxxxx`

### PASO 5 — Agregar el token como Secret en el Space
1. En tu Space ve a **Settings → Variables and secrets**
2. Clic en **New secret**
3. Nombre: `HF_TOKEN`
4. Valor: tu token `hf_xxxxxxxxxxxxxxx`
5. Guardar

### PASO 6 — Subir los archivos al Space

**Opción A — Desde la UI de HF (más fácil):**
1. En tu Space haz clic en la pestaña **Files**
2. Clic en **Add file → Upload files**
3. Sube: `main.py`, `requirements.txt`, `README.md`
4. Crea la carpeta `static/` y sube `index.html` dentro

**Opción B — Con Git (más pro):**
```bash
# Instalar git-lfs si no lo tienes
git lfs install

# Clonar tu Space vacío
git clone https://huggingface.co/spaces/TU_USUARIO/sdxl-image-forge
cd sdxl-image-forge

# Copiar tus archivos aquí
cp /ruta/a/tu/proyecto/main.py .
cp /ruta/a/tu/proyecto/requirements.txt .
cp /ruta/a/tu/proyecto/README.md .
mkdir static
cp /ruta/a/tu/proyecto/static/index.html static/

# Subir
git add .
git commit -m "Deploy SDXL Image Forge"
git push
```

### PASO 7 — Crear el Dockerfile
HF Spaces con SDK Docker necesita un `Dockerfile`.  
Crea este archivo en la raíz del Space:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

> ⚠️ HF Spaces usa el puerto **7860** por defecto.

### PASO 8 — Seleccionar GPU en el Space
1. En tu Space ve a **Settings**
2. Busca **Hardware**
3. Selecciona **ZeroGPU (A100)** ← gratis con cuenta básica
   *(o T4 small si no está disponible ZeroGPU)*
4. Guardar cambios

### PASO 9 — Esperar el build
1. HF construye la imagen Docker (~5-10 min la primera vez)
2. Luego descarga SDXL (~6 GB, tarda otros 5-10 min)
3. Cuando diga **Running** tu app está viva en:
   `https://TU_USUARIO-sdxl-image-forge.hf.space`

---

## Probar localmente antes del deploy

```bash
# Instalar dependencias (necesitas GPU con CUDA o corre en CPU lento)
pip install -r requirements.txt

# Arrancar
uvicorn main:app --reload --port 8000

# Abrir
# http://localhost:8000
# http://localhost:8000/docs  ← Swagger automático
# http://localhost:8000/health ← verifica GPU
```

---

## Endpoints

| Método | Ruta        | Descripción                             |
|--------|-------------|-----------------------------------------|
| GET    | `/`         | Frontend (index.html)                   |
| GET    | `/health`   | Estado del servidor y GPU               |
| POST   | `/generate` | Genera imagen con SDXL                  |
| GET    | `/presets`  | Prompts predefinidos por estilo         |
| GET    | `/docs`     | Swagger UI (FastAPI automático)         |

### Ejemplo `/generate`
```json
POST /generate
{
  "prompt": "burned medieval knight, glowing ember cracks, apocalyptic sky, photorealistic",
  "negative_prompt": "cartoon, anime, blurry",
  "guidance_scale": 7.5,
  "num_inference_steps": 30,
  "seed": 42,
  "width": 1024,
  "height": 1024
}
```

---

## Parámetros

| Parámetro             | Rango  | Default | Descripción                         |
|-----------------------|--------|---------|-------------------------------------|
| `guidance_scale`      | 1–20   | 7.5     | Fidelidad al prompt                 |
| `num_inference_steps` | 10–50  | 30      | Calidad (más = mejor pero más lento)|
| `seed`                | entero | null    | Reproducibilidad. null = aleatorio  |
| `width` / `height`    | 512–1024| 1024   | Resolución de salida                |

---

## Stack tecnológico

| Componente     | Herramienta                              |
|----------------|------------------------------------------|
| Modelo         | Stable Diffusion XL 1.0 (stabilityai)   |
| Framework ML   | PyTorch + Diffusers (Hugging Face)       |
| Backend        | FastAPI + Uvicorn                        |
| Frontend       | HTML / CSS / JS vanilla                  |
| Deploy         | Hugging Face Spaces (Docker + ZeroGPU)  |
