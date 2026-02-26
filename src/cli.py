"""CLI entrypoint para el pipeline de renderizado oclusal.

Uso:
    blender --background --python src/cli.py -- input.stl [output.png]
    blender --background --python src/cli.py -- input.stl --radiograph xray.png --landmarks landmarks.json [output.png]
"""
import sys
import os

# Agregar src/ al path
sys.path.insert(0, os.path.dirname(__file__))

from loader import clear_scene, load_stl
from camera import setup_occlusal_camera
from render import setup_lighting, setup_material, render_to_file


def parse_args(argv):
    """Parsea argumentos después de '--'."""
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []

    parsed = {
        'input_stl': None,
        'output_png': None,
        'radiograph': None,
        'landmarks': None,
        'auto_detect': False,
    }

    positional = []
    i = 0
    while i < len(args):
        if args[i] == '--radiograph' and i + 1 < len(args):
            parsed['radiograph'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--landmarks' and i + 1 < len(args):
            parsed['landmarks'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--auto-detect':
            parsed['auto_detect'] = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if positional:
        parsed['input_stl'] = os.path.abspath(positional[0])
    if len(positional) > 1:
        parsed['output_png'] = os.path.abspath(positional[1])
    else:
        parsed['output_png'] = os.path.abspath("output/oclusal.png")

    return parsed


def main():
    parsed = parse_args(sys.argv)

    if not parsed['input_stl']:
        print("Uso: blender --background --python src/cli.py -- <input.stl> [output.png]")
        print("  --radiograph <path>   Radiografía (DICOM, PNG, JPEG)")
        print("  --landmarks <path>    Archivo JSON con landmarks")
        print("  --auto-detect         Detectar landmarks automáticamente")
        sys.exit(1)

    input_stl = parsed['input_stl']
    output_png = parsed['output_png']

    if not os.path.exists(input_stl):
        print(f"Error: archivo no encontrado: {input_stl}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    print(f"Cargando modelo: {input_stl}")
    clear_scene()
    obj = load_stl(input_stl)
    print(f"Modelo cargado: {obj.name} ({obj.dimensions})")

    # Radiografía + registro (Phase 2)
    if parsed['radiograph']:
        _process_radiograph(parsed, obj)

    print("Configurando cámara oclusal...")
    setup_occlusal_camera(obj)

    print("Configurando iluminación y material...")
    setup_lighting()
    setup_material(obj)

    print(f"Renderizando a: {output_png}")
    render_to_file(output_png)

    print("¡Listo!")


def _process_radiograph(parsed, dental_obj):
    """Procesa radiografía: carga, overlay y registro."""
    from radiograph import load_radiograph
    from overlay import create_radiograph_plane, scale_plane_to_model, set_plane_opacity
    from registration import (
        load_landmarks_json, collect_landmarks_interactive,
        detect_landmarks_auto, compute_registration, apply_registration,
    )

    radio_path = parsed['radiograph']
    if not os.path.exists(radio_path):
        print(f"Error: radiografía no encontrada: {radio_path}")
        sys.exit(1)

    print(f"Cargando radiografía: {radio_path}")
    radio_data = load_radiograph(radio_path)
    print(f"Radiografía cargada: {radio_data['width']}x{radio_data['height']} ({radio_data['format']})")

    # Crear plano con textura
    print("Creando plano de referencia...")
    plane = create_radiograph_plane(radio_data)
    scale_plane_to_model(plane, dental_obj)
    set_plane_opacity(plane, alpha=0.7)

    # Registro con landmarks
    if parsed['landmarks']:
        print(f"Cargando landmarks: {parsed['landmarks']}")
        landmarks = load_landmarks_json(parsed['landmarks'])
    elif parsed['auto_detect']:
        print("Detectando landmarks automáticamente...")
        candidates = detect_landmarks_auto(radio_data)
        print("Nota: La detección automática sugiere candidatos en la radiografía.")
        print("      Se necesitan las coordenadas 3D correspondientes en el modelo.")
        landmarks = collect_landmarks_interactive(radio_data)
    else:
        print("Ingrese landmarks manualmente...")
        landmarks = collect_landmarks_interactive(radio_data)

    if len(landmarks['points_2d']) >= 3:
        print("Calculando registro...")
        reg = compute_registration(landmarks, radio_data['width'], radio_data['height'])
        apply_registration(plane, reg, radio_data['width'], radio_data['height'])
        print(f"Registro aplicado (error RMS: {reg['error_rms']:.6f})")
    else:
        print("Insuficientes landmarks para registro. Plano posicionado por defecto.")
        from overlay import position_plane_below
        position_plane_below(plane, dental_obj)


if __name__ == "__main__":
    main()
