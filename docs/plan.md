# POC: Guías Odontológicas 3D con Blender

## Problema
Automatizar la generación de guías quirúrgicas 3D para posicionamiento de tornillos de anclaje ortodóntico, partiendo de radiografías y modelos 3D de la boca del paciente. El proceso actual es manual y propenso a error.

## Enfoque
Pipeline incremental en Python para Blender (modo headless/CLI). Empezamos con un módulo básico de carga y renderizado, y expandimos hacia la generación de guías.

**Formatos de entrada (por definir):** Los formatos no están decididos aún. El diseño será modular para soportar distintos formatos. Para el POC inicial asumimos:
- Modelo dental: **STL** (formato más común en escáneres intraorales como iTero/3Shape)
- Radiografías: **DICOM** o imágenes 2D (se definirá en fases posteriores)

## Fases

### Fase 1 — Carga de modelo + Renderizado oclusal (MVP)
Objetivo: Demostrar que podemos cargar un STL dental en Blender headless, posicionar cámara oclusal y generar un render.

- `setup-project`: Estructura del proyecto Python, README, dependencias (bpy)
- `load-stl`: Script que carga un archivo STL en Blender, centra y escala el modelo
- `occlusal-camera`: Posicionar cámara en vista oclusal (superior, mirando hacia abajo al plano oclusal)
- `render-occlusal`: Configurar iluminación básica y renderizar imagen PNG de la vista oclusal
- `cli-entrypoint`: Script CLI que orquesta: recibe path STL → carga → renderiza → exporta PNG

### Fase 2 — Soporte de radiografías y registro
Objetivo: Incorporar datos radiográficos y alinearlos con el modelo 3D.

- `dicom-loader`: Carga y procesamiento de DICOM (o imágenes 2D como fallback)
- `image-overlay`: Superponer/mapear datos radiográficos sobre el modelo 3D
- `registration`: Registro (alineación) entre modelo dental y radiografía

### Fase 3 — Generación de guía quirúrgica
Objetivo: Generar la guía 3D imprimible para posicionamiento de tornillos.

- `screw-placement`: Interfaz/lógica para definir puntos de inserción de tornillos de anclaje
- `guide-generation`: Generar geometría de la guía quirúrgica (shell sobre el modelo dental con orificios)
- `export-stl-guide`: Exportar guía como STL listo para impresión 3D

### Fase 4 — Refinamiento y validación
- `validation`: Verificación de clearance, grosor mínimo, ajuste
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
│   └── guide.py             # (Fase 3) Generación de guía
├── samples/                 # Archivos de ejemplo (STL de prueba)
├── output/                  # Renders y guías generadas
└── tests/
    └── test_loader.py
```

## Notas
- Blender se usa headless (`blender --background --python script.py`)
- Se requiere Blender ≥ 3.x instalado en el sistema
- Para el POC se pueden usar modelos STL dentales de ejemplo (datasets públicos)
- Los formatos de entrada se definirán formalmente antes de Fase 2
