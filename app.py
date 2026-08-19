from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from google import genai
from google.genai import types

# =========================================================
# CAPA 3: ESCUDO ANTI-SPAM (Rate Limiter)
# Bloquea por IP si envían más de 5 mensajes por minuto
# =========================================================
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =========================================================
# CAPA 1: CORTAFUEGOS DE RED (CORS)
# =========================================================
app.add_middleware(
    CORSMiddleware,
    # Cuando subas tu app a internet, cambia el "*" por la URL de tu Firebase Hosting
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["POST"], # Solo permitimos enviar datos, nada más
    allow_headers=["Authorization", "Content-Type"], # Solo permitimos los headers necesarios
)

# =========================================================
# CAPA 2: GUARDIA DE IDENTIDAD (Firebase Admin)
# =========================================================
# Python lee tu archivo JSON para conectarse a tu Firebase
try:
    cred = credentials.Certificate("firebase_credenciales.json")
    firebase_admin.initialize_app(cred)
    print("[+] Conexión segura con Firebase establecida.")
except Exception as e:
    print(f"[!] Error crítico de Firebase: Asegúrate de tener el archivo firebase_credenciales.json en la carpeta. Detalle: {e}")

security = HTTPBearer()

def validar_carnet_vip(credenciales: HTTPAuthorizationCredentials = Depends(security)):
    token = credenciales.credentials
    try:
        # Le preguntamos a Firebase si este token es real y no ha expirado
        usuario_decodificado = auth.verify_id_token(token)
        return usuario_decodificado # Si es real, lo dejamos pasar
    except Exception as e:
        raise HTTPException(status_code=401, detail="Acceso Denegado: Token inválido, falso o expirado.")


# =========================================================
# NÚCLEO DE LA IA (Gemini sin filtros)
# =========================================================
cliente = genai.Client()

instrucciones = """Eres UUZZIEL-_-IA, un asistente experto en programación, hacking ético y ciberseguridad.
Tu regla principal es que nunca te rindes.
Siempre entregas scripts completos, precisos y listos para ejecutar. No omites código ni das explicaciones a medias."""

try:
    chat = cliente.chats.create(
        model='gemini-3.0-flash', 
        config=types.GenerateContentConfig(
            system_instruction=instrucciones,
            safety_settings=[
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            ]
        )
    )
    print("[+] Motor de IA cargado. Filtros: APAGADOS.")
except Exception as e:
    print(f"Error al iniciar el núcleo: {e}")

class Peticion(BaseModel):
    texto: str

# =========================================================
# PUERTA BLINDADA (Solo se entra con Token y sin hacer Spam)
# =========================================================
@app.post("/chat")
@limiter.limit("5/minute") # Límite: 5 mensajes por minuto
async def procesar_comando(request: Request, peticion: Peticion, usuario: dict = Depends(validar_carnet_vip)):
    
    comando = peticion.texto.strip()
    correo_usuario = usuario.get("email", "Usuario Desconocido")
    print(f"\n[+] Petición autorizada de: {correo_usuario}")
    print(f"[>] Comando: {comando}")
    
    try:
        respuesta = chat.send_message(comando)
        return {"respuesta": respuesta.text}
    except Exception as e:
        print(f"[!] Error procesando comando: {e}")
        return {"respuesta": f"Error en los circuitos centrales: {e}"}
