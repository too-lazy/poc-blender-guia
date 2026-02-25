"""CLI entrypoint para el pipeline de renderizado oclusal.

Uso:
    blender --background --python src/cli.py -- input.stl output.png
"""
import sys
import os

# Agregar src/ al path
sys.path.insert(0, os.path.dirname(__file__))

from loader import clear_scene, load_stl
from camera import setup_occlusal_camera
from render import setup_lighting, setup_material, render_to_file


def main():
    # Parsear argumentos después de "--"
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []

    if len(args) < 1:
        print("Uso: blender --background --python src/cli.py -- <input.stl> [output.png]")
        sys.exit(1)

    input_stl = os.path.abspath(args[0])
    output_png = os.path.abspath(args[1]) if len(args) > 1 else os.path.abspath("output/oclusal.png")

    if not os.path.exists(input_stl):
        print(f"Error: archivo no encontrado: {input_stl}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    print(f"Cargando modelo: {input_stl}")
    clear_scene()
    obj = load_stl(input_stl)
    print(f"Modelo cargado: {obj.name} ({obj.dimensions})")

    print("Configurando cámara oclusal...")
    setup_occlusal_camera(obj)

    print("Configurando iluminación y material...")
    setup_lighting()
    setup_material(obj)

    print(f"Renderizando a: {output_png}")
    render_to_file(output_png)

    print("¡Listo!")


if __name__ == "__main__":
    main()
