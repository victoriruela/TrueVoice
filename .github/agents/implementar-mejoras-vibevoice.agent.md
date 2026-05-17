---
description: "Implementar mejoras VibeVoice: chunking automático, pause tags, control de velocidad, cuantización 4/8bit, sistema de narradores, modelos personalizados, parámetros avanzados de generación. Usar cuando se pida implementar el plan de mejoras de TrueVoice."
name: "Implementar Mejoras VibeVoice"
tools: [read, edit, search, execute, todo, agent]
model: "Claude Sonnet 4.5 (copilot)"
argument-hint: "Fase o tarea específica a implementar (opcional; sin argumento implementa todo)"
---

Eres un agente de implementación experto en Python, Go y React Native/Expo para el proyecto TrueVoice.
Tu misión es implementar el **Plan de Mejoras VibeVoice** descrito en este archivo, usando Asana para trazabilidad y Git para control de cambios.

---

## REGLAS OBLIGATORIAS (leer PRIMERO)

1. **LEE `AGENTS.md` en la raíz del proyecto antes de tocar cualquier código.** Contiene la arquitectura, convenciones y reglas que no puedes violar.
2. **LEE el `AGENTS.md` de cada subdirectorio antes de modificarlo** (`truevoice-go/AGENTS.md`, `truevoice-web/AGENTS.md`).
3. **Un commit por cambio lógico** — no acumules cambios. Haz push después de cada commit de una fase completada.
4. **Ejecuta tests** después de cada fase backend Go: `cd truevoice-go && go test ./...`
5. **Ejecuta typecheck** después de cada fase frontend: `cd truevoice-web && node node_modules\typescript\bin\tsc --noEmit`
6. **No elimines ni sobreescribas archivos fuente sin verificar** que el reemplazo compila y la app carga.
7. **No despliegues a producción** — solo deploy local para pruebas al final.

---

## SETUP INICIAL

### 1. Verificar rama de trabajo

```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice
git branch --show-current  # debe ser 'develop' o una feature branch ya creada
```

Todas las feature branches se crean desde `develop` y se mergean a `develop`.

### 2. Configurar Asana

El proyecto TrueVoice ya existe en Asana:
- **Project GID**: `1213903547619538`
- **Workspace GID**: `1213846793386214`
- **Sección Pending GID**: `1213903547619566`
- **Sección In Progress GID**: `1213902454337091`
- **Sección In Hold GID**: `1213902454337092`
- **Sección Done GID**: `1213902454337093`

**Al iniciar cada fase:**
1. Crea una tarea en Asana con `mcp_asana-mcp-api_create_task` en la sección `Pending`.
2. Muévela a `In Progress` con `mcp_asana-mcp-api_add_task_to_section` al empezar.
3. Muévela a `Done` al completar la fase y hacer push.

Si falla la autenticación Asana (`invalid_token`):
```powershell
python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" auth
python "$env:USERPROFILE\.claude\asana-mcp\scripts\asana_mcp.py" update-mcp --target copilot-vscode
# Luego reintentar la herramienta MCP
```

### 3. Crear subtareas Asana por fase

Crea las siguientes tareas en el proyecto (sección Pending), **antes de empezar la implementación**:
1. "F1: inference_wrapper.py — chunking, pause tags, speed, quantization, params"
2. "F2: vibevoice_app.py — nuevos args CLI y modo multi-speaker"
3. "F3: Go config.go + generation.go — nuevos campos y lógica narradores"
4. "F4: Go endpoints /narrators y /models"
5. "F5: Frontend useConfigStore.ts — nuevos campos"
6. "F6: Frontend voices.tsx — sección narradores"
7. "F7: Frontend settings.tsx — parámetros avanzados y modelos custom"
8. "F8: Frontend generar.tsx — hint multi-speaker"
9. "F9: requirements.txt + bootstrap.go — bitsandbytes"
10. "F10: Build, tests y dist/TrueVoice_Pruebas"

---

## ESTRATEGIA DE BRANCHES (para paralelización)

Crea estas branches desde `develop`. Cada una puede ser trabajada por un agente independiente:

| Branch | Fases | Dependencias |
|--------|-------|--------------|
| `feat/vibevoice-sidecar` | F1 + F2 | Ninguna |
| `feat/deps-quantization` | F9 | Ninguna |
| `feat/backend-narrators-models` | F3 + F4 | F1+F2 (API design) |
| `feat/frontend-advanced-params` | F5 + F6 + F7 + F8 | F3+F4 (API design) |

Merge order a `develop`: deps-quantization → vibevoice-sidecar → backend-narrators-models → frontend-advanced-params → build final.

```powershell
# Crear branch:
git checkout develop
git pull origin develop
git checkout -b feat/vibevoice-sidecar
```

---

## PLAN DE IMPLEMENTACIÓN DETALLADO

### FASE 1 — `inference_wrapper.py` · Motor de generación Python
**Branch:** `feat/vibevoice-sidecar`

**Nuevos argumentos CLI a añadir:**
```python
parser.add_argument("--temperature", type=float, default=0.95)
parser.add_argument("--top_p", type=float, default=0.95)
parser.add_argument("--use_sampling", action="store_true", default=False)
parser.add_argument("--quantize_llm", type=str, default="none",
                    choices=["none", "4bit", "8bit"])
parser.add_argument("--voice_speed_factor", type=float, default=1.0)
parser.add_argument("--max_words_per_chunk", type=int, default=250)
```

**Voice speed control** — aplicar ANTES de construir `inputs`:
```python
# En la función main(), tras cargar voice_samples, antes de processor(...)
if args.voice_speed_factor != 1.0:
    import librosa
    import soundfile as sf
    import tempfile
    new_voice_samples = []
    for vpath in voice_samples:
        if vpath and os.path.exists(vpath):
            audio, sr = librosa.load(vpath, sr=None, mono=True)
            stretched = librosa.effects.time_stretch(audio, rate=args.voice_speed_factor)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sf.write(tmp.name, stretched, sr)
            new_voice_samples.append(tmp.name)
        else:
            new_voice_samples.append(vpath)
    voice_samples = new_voice_samples
```

**Cuantización dinámica** — modificar la carga del modelo:
```python
# Solo si device=cuda y quantize_llm != "none"
quantization_config = None
if args.device == "cuda" and args.quantize_llm != "none":
    try:
        from transformers import BitsAndBytesConfig
        if args.quantize_llm == "4bit":
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
        elif args.quantize_llm == "8bit":
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    except ImportError:
        print("WARNING: bitsandbytes no disponible, ignorando cuantización", flush=True)

model = VibeVoiceForConditionalGenerationInference.from_pretrained(
    args.model_path,
    torch_dtype=load_dtype,
    device_map=args.device,
    attn_implementation=attn_impl,
    low_cpu_mem_usage=True,
    quantization_config=quantization_config,  # None si no aplica
)
```

**Temperatura/top_p/use_sampling** — modificar `model.generate()`:
```python
outputs = model.generate(
    **inputs,
    max_new_tokens=None,
    cfg_scale=args.cfg_scale,
    tokenizer=processor.tokenizer,
    generation_config={
        'do_sample': args.use_sampling,
        'temperature': args.temperature if args.use_sampling else None,
        'top_p': args.top_p if args.use_sampling else None,
    },
    is_prefill=not args.disable_prefill,
)
```

**Pause tags** — añadir función de preprocesado de texto Y de generación por fragmentos:
```python
import re as _re
import numpy as _np

def parse_pause_tags(text: str):
    """
    Divide el texto en segmentos y silencios.
    Retorna lista de ('text', str) o ('silence', ms_int).
    """
    parts = []
    pattern = _re.compile(r'\[pause(?::(\d+))?\]', _re.IGNORECASE)
    last = 0
    for m in pattern.finditer(text):
        seg = text[last:m.start()].strip()
        if seg:
            parts.append(('text', seg))
        ms = int(m.group(1)) if m.group(1) else 1000
        parts.append(('silence', ms))
        last = m.end()
    tail = text[last:].strip()
    if tail:
        parts.append(('text', tail))
    return parts if parts else [('text', text)]
```

Cuando el texto tiene pause tags, generar cada fragmento de texto por separado y concatenar con silencios de numpy/torch.

**Chunking automático** — añadir función de chunking por palabras:
```python
def chunk_text_by_words(text: str, max_words: int):
    """Divide en frases respetando puntuación, sin superar max_words palabras."""
    sentences = _re.split(r'(?<=[.!?])\s+', text)
    chunks, current, count = [], [], 0
    for sent in sentences:
        words = len(sent.split())
        if count + words > max_words and current:
            chunks.append(' '.join(current))
            current, count = [sent], words
        else:
            current.append(sent)
            count += words
    if current:
        chunks.append(' '.join(current))
    return chunks if chunks else [text]
```

Integrar chunking en el flujo: si el texto de un speaker supera `max_words_per_chunk`, dividirlo en bloques, generar cada uno con el mismo seed, y concatenar los tensores de audio con `torch.cat`.

**Commit tras Fase 1:**
```powershell
git add inference_wrapper.py
git commit -m "feat(inference): chunking, pause tags, voice speed, quantization, temperature/top_p"
git push origin feat/vibevoice-sidecar
```

---

### FASE 2 — `vibevoice_app.py` · CLI frontend
**Branch:** `feat/vibevoice-sidecar` (continuar en la misma)

**Cambios necesarios:**

1. Añadir nuevos args CLI:
```python
parser.add_argument("--voice-speed-factor", type=float, default=1.0)
parser.add_argument("--max-words-per-chunk", type=int, default=250)
parser.add_argument("--quantize-llm", type=str, default="none",
                    choices=["none", "4bit", "8bit"])
parser.add_argument("--temperature", type=float, default=0.95)
parser.add_argument("--top-p", type=float, default=0.95)
parser.add_argument("--use-sampling", action="store_true", default=False)
```

2. Cambiar `--voice-name` a `nargs='+'` para aceptar múltiples rutas de voz.

3. Añadir flag `--multi-speaker` (bool): cuando está presente, el texto ya viene en formato
   `Speaker N:` (enviado desde Go) → NO envolver en `Speaker 1:`.

4. En `generate_speech_vibevoice()` (o función equivalente), lógica:
   - Si `--multi-speaker`: escribir el texto tal cual al temp file.
   - Si single speaker (default): comportamiento actual (envuelve en `Speaker 1: {text}`).
   - Si múltiples voces: pasar a inference_wrapper como `--speaker_names v1 v2 v3`.

5. Pasar todos los nuevos args al subprocess `inference_wrapper.py`:
```python
cmd += [
    "--voice_speed_factor", str(args.voice_speed_factor),
    "--max_words_per_chunk", str(args.max_words_per_chunk),
    "--quantize_llm", args.quantize_llm,
    "--temperature", str(args.temperature),
    "--top_p", str(args.top_p),
]
if args.use_sampling:
    cmd.append("--use_sampling")
```

**Commit tras Fase 2:**
```powershell
git add vibevoice_app.py
git commit -m "feat(sidecar): nuevos args CLI, modo multi-speaker, múltiples voces"
git push origin feat/vibevoice-sidecar
```

Mergear `feat/vibevoice-sidecar` → `develop`:
```powershell
git checkout develop
git merge feat/vibevoice-sidecar
git push origin develop
```

---

### FASE 9 — `requirements.txt` + `bootstrap.go` (PARALELA, sin dependencias)
**Branch:** `feat/deps-quantization`

**`requirements.txt`:** añadir al final:
```
bitsandbytes>=0.48.1
```

**`truevoice-go/internal/generation/bootstrap.go`:** en la lista de paquetes pip a instalar, añadir `"bitsandbytes>=0.48.1"` junto a las otras dependencias.

**Commit:**
```powershell
git add requirements.txt truevoice-go/internal/generation/bootstrap.go
git commit -m "build(deps): add bitsandbytes>=0.48.1 for dynamic quantization support"
git push origin feat/deps-quantization
```

Mergear → `develop`.

---

### FASE 3 — Go `config.go` + `generation.go` · Campos nuevos + lógica narradores
**Branch:** `feat/backend-narrators-models`

#### 3a. `truevoice-go/internal/config/config.go`

Añadir al struct `AppConfig`:
```go
// Parámetros de generación avanzada
VoiceSpeedFactor    float64          `json:"voice_speed_factor"`
MaxWordsPerChunk    int              `json:"max_words_per_chunk"`
QuantizeLLM         string           `json:"quantize_llm"`
Temperature         float64          `json:"temperature"`
TopP                float64          `json:"top_p"`
UseSampling         bool             `json:"use_sampling"`

// Sistema de narradores
Narrators           []NarratorConfig `json:"narrators"`

// Modelos personalizados
CustomModels        []CustomModel    `json:"custom_models"`
```

Añadir structs nuevos en el mismo archivo:
```go
type NarratorConfig struct {
    Key         string `json:"key"`          // clave única ej: "principal", "carlos"
    Name        string `json:"name"`         // nombre para display
    Voice       string `json:"voice"`        // ruta o nombre de voz (.wav)
    IsPrincipal bool   `json:"is_principal"`
    SpeakerSlot int    `json:"speaker_slot"` // 1-4, para "Speaker N:"
}

type CustomModel struct {
    ID   string `json:"id"`   // path local absoluto o HF repo ID
    Name string `json:"name"` // nombre para display en UI
    Size string `json:"size"` // ej: "~6 GB" (informativo)
}
```

Defaults en la función de defaults existente:
```go
"voice_speed_factor":    1.0,
"max_words_per_chunk":   250,
"quantize_llm":          "none",
"temperature":           0.95,
"top_p":                 0.95,
"use_sampling":          false,
"narrators":             []NarratorConfig{},
"custom_models":         []CustomModel{},
```

#### 3b. `truevoice-go/internal/generation/generation.go`

Añadir campos a `GenerateRequest`:
```go
VoiceSpeedFactor    float64  `json:"voice_speed_factor"`
MaxWordsPerChunk    int      `json:"max_words_per_chunk"`
QuantizeLLM         string   `json:"quantize_llm"`
Temperature         float64  `json:"temperature"`
TopP                float64  `json:"top_p"`
UseSampling         bool     `json:"use_sampling"`
Seed                *int     `json:"seed"`
VoiceNames          []string `json:"voice_names"` // multi-speaker: voces en orden de slot
```

Defaults aplicados en `GenerateHandler` para los nuevos campos:
```go
if req.VoiceSpeedFactor == 0 { req.VoiceSpeedFactor = 1.0 }
if req.MaxWordsPerChunk == 0  { req.MaxWordsPerChunk = cfg.MaxWordsPerChunk }
if req.QuantizeLLM == ""      { req.QuantizeLLM = cfg.QuantizeLLM }
if req.Temperature == 0       { req.Temperature = cfg.Temperature }
if req.TopP == 0              { req.TopP = cfg.TopP }
```

**Lógica de narradores en `GenerateHandler`:**

```go
// Detectar marcadores [key]: en el texto
narratorTagRe := regexp.MustCompile(`\[([^\]]+)\]:`)
narrators := cfg.Narrators

if narratorTagRe.MatchString(req.Text) && len(narrators) > 0 {
    // Construir mapa key → NarratorConfig
    narratorMap := map[string]NarratorConfig{}
    for _, n := range narrators {
        narratorMap[n.Key] = n
    }
    
    // Convertir [key]: → Speaker N: y construir lista de voces
    processedText := narratorTagRe.ReplaceAllStringFunc(req.Text, func(match string) string {
        key := narratorTagRe.FindStringSubmatch(match)[1]
        if n, ok := narratorMap[key]; ok {
            return fmt.Sprintf("Speaker %d:", n.SpeakerSlot)
        }
        return match // dejar sin cambios si no se encuentra
    })
    req.Text = processedText
    req.MultiSpeaker = true  // flag para vibevoice_app.py

    // Ordenar voces por speaker_slot y resolver paths
    slotVoiceMap := map[int]string{}
    for _, n := range narrators {
        if _, used := narratorMap[n.Key]; used {
            slotVoiceMap[n.SpeakerSlot] = n.Voice
        }
    }
    // Construir slice ordenado de voces (slots 1..maxSlot)
    maxSlot := 0
    for slot := range slotVoiceMap { if slot > maxSlot { maxSlot = slot } }
    voiceNames := make([]string, maxSlot)
    for slot, voice := range slotVoiceMap {
        resolvedPath, _ := m.voices.Resolve(voice)
        voiceNames[slot-1] = resolvedPath
    }
    req.VoiceNames = voiceNames

} else if len(narrators) > 0 {
    // Sin marcadores: usar narrador principal si está configurado
    for _, n := range narrators {
        if n.IsPrincipal {
            if req.VoiceName == "" || req.VoiceName == "Alice" {
                req.VoiceName = n.Voice
            }
            break
        }
    }
}
```

Añadir campo `MultiSpeaker bool` a `GenerateRequest` y pasarlo como `--multi-speaker` al subprocess cuando sea `true`.

Actualizar construcción del comando subprocess para incluir todos los nuevos args:
```go
args = append(args,
    "--voice-speed-factor", fmt.Sprintf("%.2f", req.VoiceSpeedFactor),
    "--max-words-per-chunk", strconv.Itoa(req.MaxWordsPerChunk),
    "--quantize-llm", req.QuantizeLLM,
    "--temperature", fmt.Sprintf("%.2f", req.Temperature),
    "--top-p", fmt.Sprintf("%.2f", req.TopP),
)
if req.UseSampling  { args = append(args, "--use-sampling") }
if req.MultiSpeaker { args = append(args, "--multi-speaker") }
if req.Seed != nil  { args = append(args, "--seed", strconv.Itoa(*req.Seed)) }

// Multi-speaker: múltiples --voice-name
if len(req.VoiceNames) > 0 {
    for _, vn := range req.VoiceNames {
        args = append(args, "--voice-name", vn)
    }
} else {
    args = append(args, "--voice-name", voicePath)
}
```

**Commit tras Fase 3:**
```powershell
git add truevoice-go/internal/config/config.go truevoice-go/internal/generation/generation.go
git commit -m "feat(backend): narrator system, custom models config, advanced generation params"
cd truevoice-go ; go build ./... ; go test ./...
git push origin feat/backend-narrators-models
```

---

### FASE 4 — Go nuevos endpoints `/narrators` y `/models`
**Branch:** `feat/backend-narrators-models` (continuar)

Añadir en el router (`truevoice-go/internal/server/`):
```
GET    /narrators           → listNarrators
POST   /narrators           → createOrUpdateNarrator
PUT    /narrators/{key}     → updateNarrator
DELETE /narrators/{key}     → deleteNarrator
POST   /narrators/{key}/set-principal → setPrincipalNarrator
POST   /models              → addCustomModel
DELETE /models/{id}         → deleteCustomModel (id URL-encoded)
```

**`GET /narrators`:** devuelve `cfg.Narrators` como JSON array.

**`POST /narrators`:** body `NarratorConfig`, añade o actualiza (si `key` ya existe) en `cfg.Narrators`, guarda config.

**`PUT /narrators/{key}`:** actualiza campos del narrador con esa clave.

**`DELETE /narrators/{key}`:** elimina narrador con esa clave de la lista.

**`POST /narrators/{key}/set-principal`:** marca ese narrador como `is_principal=true` y todos los demás como `false`.

**Actualizar `GET /models`** para incluir los 4 modelos built-in + custom models del config:
```go
func (s *Server) listModels(w http.ResponseWriter, r *http.Request) {
    builtIns := []map[string]string{
        {"id": "microsoft/VibeVoice-1.5b", "name": "VibeVoice 1.5B (recomendado)", "size": "~6 GB"},
        {"id": "aoi-ot/VibeVoice-Large",    "name": "VibeVoice Large (máx. calidad)", "size": "~18.7 GB"},
        {"id": "FabioSarracino/VibeVoice-Large-Q8", "name": "VibeVoice Large Q8 (equilibrado)", "size": "~11.6 GB"},
        {"id": "DevParker/VibeVoice7b-low-vram", "name": "VibeVoice Large Q4 (VRAM reducida)", "size": "~6.6 GB"},
    }
    cfg := s.config.Get()
    models := builtIns
    for _, cm := range cfg.CustomModels {
        models = append(models, map[string]string{
            "id": cm.ID, "name": cm.Name, "size": cm.Size,
        })
    }
    writeJSON(w, http.StatusOK, models)
}
```

**`POST /models`:** body `CustomModel`, añade a `cfg.CustomModels`, guarda config.

**`DELETE /models/{id}`:** elimina por ID (URL-decode el ID), guarda config.

**Commit tras Fase 4:**
```powershell
git add truevoice-go/
git commit -m "feat(api): endpoints CRUD para narradores y modelos personalizados"
cd truevoice-go ; go build ./... ; go test ./...
git push origin feat/backend-narrators-models
```

Mergear `feat/backend-narrators-models` → `develop`:
```powershell
git checkout develop
git merge feat/backend-narrators-models
git push origin develop
```

---

### FASE 5 — Frontend `useConfigStore.ts`
**Branch:** `feat/frontend-advanced-params`

Añadir al tipo `AppConfig` (TypeScript):
```typescript
voice_speed_factor: number         // 1.0
max_words_per_chunk: number        // 250
quantize_llm: string               // "none" | "4bit" | "8bit"
temperature: number                // 0.95
top_p: number                      // 0.95
use_sampling: boolean              // false
narrators: NarratorConfig[]        // []
custom_models: CustomModel[]       // []
```

Añadir interfaces TypeScript:
```typescript
export interface NarratorConfig {
  key: string
  name: string
  voice: string
  is_principal: boolean
  speaker_slot: number
}

export interface CustomModel {
  id: string
  name: string
  size: string
}
```

Añadir a los defaults del store:
```typescript
voice_speed_factor: 1.0,
max_words_per_chunk: 250,
quantize_llm: 'none',
temperature: 0.95,
top_p: 0.95,
use_sampling: false,
narrators: [],
custom_models: [],
```

Añadir métodos específicos para narradores:
```typescript
// Métodos narrador
fetchNarrators: async () => { /* GET /narrators → patch narrators */ }
addNarrator: async (n: NarratorConfig) => { /* POST /narrators */ }
updateNarrator: async (key: string, n: Partial<NarratorConfig>) => { /* PUT /narrators/{key} */ }
deleteNarrator: async (key: string) => { /* DELETE /narrators/{key} */ }
setPrincipalNarrator: async (key: string) => { /* POST /narrators/{key}/set-principal */ }

// Métodos modelo custom
addCustomModel: async (m: CustomModel) => { /* POST /models */ }
deleteCustomModel: async (id: string) => { /* DELETE /models/{id} */ }
```

**Commit:**
```powershell
git add truevoice-web/src/stores/useConfigStore.ts
git commit -m "feat(store): narrator system, custom models, advanced generation params"
cd truevoice-web ; node node_modules\typescript\bin\tsc --noEmit
git push origin feat/frontend-advanced-params
```

---

### FASE 6 — Frontend `voices.tsx` · Sección Narradores
**Branch:** `feat/frontend-advanced-params` (continuar)

Añadir una sección "Narradores" **al principio** de la pantalla de Voces (antes de la lista de voces), usando el mismo sistema de estilos del archivo (`theme`, colores `primary`, `surface`, etc.).

**Estructura UI de la sección:**

```
[Narradores]                                [+ Añadir narrador]

┌─────────────────────────────────────────┐
│ 👤 Carlos          #carlos   Slot 1     │
│   Voz: carlos.wav             [PRINCIPAL]│
│                              [Eliminar] │
├─────────────────────────────────────────┤
│ 👤 María           #maria    Slot 2     │
│   Voz: maria.wav              Secundario│
│                         [Principal][x] │
└─────────────────────────────────────────┘
```

**Formulario "Añadir narrador"** (expandible al pulsar "+ Añadir narrador"):
- Campo "Nombre": TextInput
- Campo "Clave" (key): TextInput — único, sin espacios, se usa como `[clave]:` en el texto
- Selector "Voz": Picker/dropdown con la lista de voces disponibles (reutilizar `voices` del store)
- Selector "Slot" (1-4): Picker numérico
- Toggle "Narrador principal"
- Botón "Guardar narrador"

Usar `useConfigStore` para operaciones de narradores. Mostrar un estado vacío con instrucción si no hay narradores configurados.

Nota informativa visible en la sección: *"El narrador principal se usa cuando no se especifica narrador. En textos multi-speaker, usa `[clave]: texto`"*

**Commit:**
```powershell
git add truevoice-web/app/voices.tsx
git commit -m "feat(voices): sección narradores con CRUD completo y selector de voz"
cd truevoice-web ; node node_modules\typescript\bin\tsc --noEmit
git push origin feat/frontend-advanced-params
```

---

### FASE 7 — Frontend `settings.tsx` · Parámetros avanzados + Modelos custom
**Branch:** `feat/frontend-advanced-params` (continuar)

**Nueva sección "Generación avanzada"** (añadir después de la sección de síntesis existente con CFG/DDPM):

```tsx
{/* Velocidad de voz */}
<Slider label="Velocidad de voz" value={cfg.voice_speed_factor}
        min={0.8} max={1.2} step={0.01}
        onChange={(v) => patch({ voice_speed_factor: v })} />

{/* Palabras por bloque (chunking) */}
<Slider label="Palabras por bloque" value={cfg.max_words_per_chunk}
        min={100} max={500} step={10}
        onChange={(v) => patch({ max_words_per_chunk: v })} />

{/* Cuantización */}
<Dropdown label="Cuantización LLM" value={cfg.quantize_llm}
          options={[
            { label: "Precisión completa", value: "none" },
            { label: "4-bit (ahorro VRAM, req. GPU CUDA)", value: "4bit" },
            { label: "8-bit (equilibrado, req. GPU CUDA)", value: "8bit" },
          ]}
          onChange={(v) => patch({ quantize_llm: v })} />
<Text style={styles.dimText}>La cuantización solo funciona con GPU CUDA.</Text>

{/* Modo sampling */}
<Toggle label="Modo sampling (variación creativa)"
        value={cfg.use_sampling}
        onChange={(v) => patch({ use_sampling: v })} />
{cfg.use_sampling && <>
  <Slider label="Temperature" value={cfg.temperature}
          min={0.1} max={2.0} step={0.05}
          onChange={(v) => patch({ temperature: v })} />
  <Slider label="Top-p" value={cfg.top_p}
          min={0.1} max={1.0} step={0.05}
          onChange={(v) => patch({ top_p: v })} />
</>}
```

**Nueva sección "Modelos personalizados"** (añadir después de la selección de modelo actual):

```tsx
{/* Lista de modelos custom */}
{cfg.custom_models.map(m => (
  <ModelCard key={m.id} model={m}
             onDelete={() => deleteCustomModel(m.id)} />
))}

{/* Formulario añadir modelo */}
<AddModelForm onAdd={(m) => addCustomModel(m)} />
```

El `AddModelForm` tiene dos campos: "Nombre" y "ID / Ruta local", y un botón "Añadir". La ruta puede ser un HF repo ID (`microsoft/VibeVoice-1.5b`) o una ruta absoluta a una carpeta local.

**Commit:**
```powershell
git add truevoice-web/app/settings.tsx
git commit -m "feat(settings): parámetros avanzados de generación y gestión de modelos custom"
cd truevoice-web ; node node_modules\typescript\bin\tsc --noEmit
git push origin feat/frontend-advanced-params
```

---

### FASE 8 — Frontend `generar.tsx` · Hint multi-speaker
**Branch:** `feat/frontend-advanced-params` (continuar)

Añadir un icono de información `ℹ` junto al label del textarea de texto en cada `TaskCard`. Al pulsarlo, mostrar un `Modal` (o un tooltip en web) con:

```
── Formato multi-speaker ──────────────────────
Speaker 1: Buenos días a todos
Speaker 2: Y bienvenidos al Gran Premio de Japón

Los narradores se configuran en la pestaña Voces.
Los números corresponden al "Slot" de cada narrador.
───────────────────────────────────────────────
[Insertar ejemplo]   [Cerrar]
```

El botón "Insertar ejemplo" rellena el textarea con el texto de ejemplo. Usar el mismo patrón de Modal que ya exista en el proyecto, o uno básico con `Modal` de React Native.

**Commit:**
```powershell
git add truevoice-web/app/generar.tsx
git commit -m "feat(generar): hint multi-speaker con formato y botón insertar ejemplo"
cd truevoice-web ; node node_modules\typescript\bin\tsc --noEmit
git push origin feat/frontend-advanced-params
```

Mergear `feat/frontend-advanced-params` → `develop`:
```powershell
git checkout develop
git merge feat/frontend-advanced-params
git push origin develop
```

---

### FASE 10 — Build, Tests y `dist/TrueVoice_Pruebas`
**Branch:** `develop` (directamente)

#### 10a. TypeScript check
```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice\truevoice-web
node node_modules\typescript\bin\tsc --noEmit
```
Si hay errores → corregirlos antes de continuar.

#### 10b. Export frontend
```powershell
node node_modules\.bin\expo.cmd export --platform web
```

#### 10c. Copiar webdist al backend
```powershell
$src = "C:\Users\the_h\PycharmProjects\TrueVoice\truevoice-web\dist"
$dst = "C:\Users\the_h\PycharmProjects\TrueVoice\truevoice-go\internal\server\webdist"
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
New-Item -ItemType Directory -Path $dst | Out-Null
Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force
```

#### 10d. Build + tests Go
```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice\truevoice-go
go build ./...
go test ./...
```

#### 10e. Arrancar servidor en local para verificar
```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice\truevoice-go
go run .\cmd\truevoice
# Abrir http://localhost:8000/app y verificar:
# - Pestaña Voces: sección Narradores visible, formulario funciona
# - Pestaña Config: nueva sección "Generación avanzada" con sliders
# - Pestaña Config: sección "Modelos personalizados"
# - Pestaña Generar: icono ℹ con hint multi-speaker
# - La selección de modelo muestra Large / Q8 / Q4
```

#### 10f. Regenerar dist/TrueVoice_Pruebas
```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice\dist
powershell -ExecutionPolicy Bypass -File .\build_pruebas.ps1
```

#### 10g. Commit final
```powershell
cd C:\Users\the_h\PycharmProjects\TrueVoice
git add .
git commit -m "build: rebuild webdist y TrueVoice_Pruebas tras implementación de mejoras VibeVoice"
git push origin develop
```

---

## RESUMEN DE ARCHIVOS MODIFICADOS

| Archivo | Fase | Descripción del cambio |
|---------|------|----------------------|
| `inference_wrapper.py` | F1 | Chunking, pause tags, voice speed, quantization, temperature/top_p |
| `vibevoice_app.py` | F2 | Nuevos args CLI, multi-speaker mode, múltiples voces |
| `truevoice-go/internal/config/config.go` | F3 | NarratorConfig, CustomModel, nuevos campos AppConfig |
| `truevoice-go/internal/generation/generation.go` | F3 | Nuevos campos request, lógica narradores, nuevos subprocess args |
| `truevoice-go/internal/server/` | F4 | Nuevos handlers narradores y modelos custom |
| `requirements.txt` | F9 | bitsandbytes>=0.48.1 |
| `truevoice-go/internal/generation/bootstrap.go` | F9 | bitsandbytes en pip install |
| `truevoice-web/src/stores/useConfigStore.ts` | F5 | Tipos y métodos nuevos |
| `truevoice-web/app/voices.tsx` | F6 | Sección narradores |
| `truevoice-web/app/settings.tsx` | F7 | Parámetros avanzados + modelos custom |
| `truevoice-web/app/generar.tsx` | F8 | Hint multi-speaker |

---

## CONSIDERACIONES IMPORTANTES

1. **bitsandbytes en CPU**: se instala igualmente pero la cuantización se ignora si no hay CUDA.
   La UI muestra "req. GPU CUDA" — no bloquear el campo, solo informar.

2. **Compatibilidad hacia atrás**: si no hay narradores configurados, el sistema usa `selected_voice`
   y `VoiceName` exactamente igual que antes. Cero regresiones.

3. **VoiceName vs VoiceNames**: mantener `VoiceName` (string) para single-speaker y añadir
   `VoiceNames` ([]string) para multi-speaker. Usar uno u otro en el subprocess según `MultiSpeaker`.

4. **Chunking y pause tags**: si el texto tiene AMBOS, procesar pause tags primero (split en
   segmentos), y luego aplicar chunking a cada segmento de texto si supera max_words_per_chunk.

5. **Modelos Large sin bootstrap automático**: mostrarlos en el selector pero NO cambiar el
   bootstrap para descargarlos automáticamente. El usuario los descarga manualmente o via HF CLI.
