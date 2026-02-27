# POC: Guías Odontológicas 3D con Blender

## Problema
Automatizar la generación de guías quirúrgicas 3D para posicionamiento de tornillos de anclaje ortodóntico, partiendo de radiografías y modelos 3D de la boca del paciente. El proceso actual es manual y propenso a error.

## Enfoque
Pipeline incremental en Python para Blender (modo headless/CLI). Empezamos con un módulo básico de carga y renderizado, y expandimos hacia la generación de guías.

## Definiciones técnicas confirmadas

| Parámetro | Decisión | Notas |
|-----------|----------|-------|
| **Radiografías** | CBCT / DICOM | Volúmenes 3D multi-slice (ej. Sirona: 672 cortes axiales, 0.22mm isotrópico) |
| **Escáner intraoral** | iTero | Exporta STL binario, dos archivos por caso (arco superior `_u` + inferior `_l_bite`) |
| **Colocación de tornillos** | Manual | El clínico define puntos de inserción interactivamente (no se requiere IA) |
| **Impresora 3D** | MSLA (resina) | Resolución XY ~35-50µm, altura de capa 25-100µm. Compensar contracción de resina (~0.5-1%) |

### Formatos de entrada

- **Modelo dental:** STL binario desde iTero (ej. `275588435_shell_occlusion_u.stl`, `_l_bite1.stl`)
- **Radiografía CBCT:** DICOM multi-slice sin extensión (directorio de archivos numerados, serie CTVolume)
- **Orden de laboratorio:** PDF con especificaciones del caso (informativo, no procesado automáticamente)

### Ejemplo de datos reales (`/input`)

```
input/
├── STL/                          # Escáner intraoral iTero
│   ├── 275588435_shell_occlusion_u.stl       # Arco superior (491K triángulos, 23MB)
│   ├── 275588435_shell_occlusion_l_bite1.stl  # Arco inferior + mordida (357K triángulos, 17MB)
│   └── Orden Laboratorio1.pdf                 # Orden de laboratorio
└── RXs/DICOMRM/                  # CBCT Sirona
    └── .../154051/
        ├── CT3/000..671          # Volumen CT principal (672 slices, 800x800, 16-bit, 0.22mm)
        ├── CT2,CT4-CT8/          # Proyecciones 2D derivadas (8-bit, informativas)
        ├── COMP0,COMP1/          # RawBlobs internos Sirona (no se usan)
        └── RAWEXAM1/             # ExamDump (no se usa)
```

## Fases

### Fase 1 — Carga de modelo + Renderizado oclusal (MVP) ✅
Objetivo: Demostrar que podemos cargar un STL dental en Blender headless, posicionar cámara oclusal y generar un render.

- ✅ `setup-project`: Estructura del proyecto Python, README, dependencias (bpy)
- ✅ `load-stl`: Script que carga un archivo STL en Blender, centra y escala el modelo
- ✅ `occlusal-camera`: Posicionar cámara en vista oclusal (superior, mirando hacia abajo al plano oclusal)
- ✅ `render-occlusal`: Configurar iluminación básica y renderizar imagen PNG de la vista oclusal
- ✅ `cli-entrypoint`: Script CLI que orquesta: recibe path STL → carga → renderiza → exporta PNG

### Fase 2 — Soporte de radiografías y registro ⚠️ (parcial)
Objetivo: Incorporar datos radiográficos CBCT y alinearlos con el modelo 3D.

- ✅ `dicom-loader`: Carga DICOM single-slice (pydicom) y 2D (OpenCV/Pillow), normalización → `src/radiograph.py`
- ✅ `cbct-volume-loader`: Carga de serie DICOM multi-slice como volumen 3D → `src/radiograph.py:load_dicom_series()`
- ✅ `itero-dual-arch`: Carga simultánea de arco superior e inferior desde iTero → `src/loader.py:load_dual_arch()`
- ✅ `image-overlay`: Plano de referencia texturizado en escena Blender con opacidad → `src/overlay.py`
- ✅ `registration`: Landmarks interactivos/JSON + auto-detección OpenCV + registro least-squares → `src/registration.py`

### Fase 3 — Generación de guía quirúrgica ✅
Objetivo: Generar la guía 3D imprimible para posicionamiento de tornillos.

- ✅ `screw-placement`: Interfaz manual para definir puntos de inserción de tornillos de anclaje (visor 3D interactivo con raycasting, click para colocar tornillos en la superficie del modelo)
- ✅ `guide-generation`: Generar geometría de la guía quirúrgica (shell/offset del modelo dental con cilindros guía en cada punto de tornillo) → `src/guide.py`
- ✅ `export-stl-guide`: Exportar guía como STL listo para impresión MSLA (compensación contracción 0.5%, gap de ajuste 80µm, espesor mínimo 2.5mm)

### Fase 4 — Refinamiento y validación
- `msla-preflight`: Verificación de imprimibilidad MSLA (espesor mínimo, ángulos sin soporte, compensación contracción)
- `validation`: Verificación de clearance con raíces, grosor mínimo, ajuste sobre modelo
- `batch-processing`: Soporte para múltiples casos
- `documentation`: Documentación de uso clínico

## Estructura propuesta del proyecto

```
poc-blender-guia/
├── README.md
├── requirements.txt
├── docs/
│   └── plan.md
├── src/
│   ├── __init__.py
│   ├── cli.py              # Entrypoint CLI
│   ├── loader.py            # Carga de STL/modelos
│   ├── camera.py            # Configuración de cámara oclusal
│   ├── render.py            # Renderizado
│   ├── radiograph.py        # Carga de radiografías (DICOM/2D)
│   ├── overlay.py           # Plano de referencia con textura
│   ├── registration.py      # Registro basado en landmarks
│   └── guide.py             # (Fase 3) Generación de guía
├── samples/                 # Archivos de ejemplo (STL, radiografías, landmarks)
├── output/                  # Renders y guías generadas
└── tests/
    └── test_loader.py
```

## Notas
- Blender se usa headless (`blender --background --python script.py`)
- Se requiere Blender ≥ 5.0 instalado en el sistema (`bpy.ops.wm.stl_import`)
- Los datos de entrada reales están en `/input` (iTero STLs + CBCT Sirona)
- Archivos DICOM sin extensión: la detección se hace por magic number `DICM` en offset 128
- iTero exporta STL binario en mm con coordenadas ya en orientación dental estándar
- Serie DICOM relevante: solo CT3 (CTVolume, ORIGINAL/PRIMARY/AXIAL). Las series CT2/CT4-CT8 son proyecciones 2D derivadas. COMP0/COMP1/RAWEXAM1 son datos internos Sirona (ignorar)
- Para impresión MSLA: compensar contracción de resina dental (0.5-1%), espesor mínimo de pared ≥ 1mm, ajuste sobre modelo dental con gap de 50-100µm
