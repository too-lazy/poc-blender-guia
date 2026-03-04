"""CLI entrypoint para el pipeline de renderizado oclusal y generación de guías.

Uso:
    blender --background --python src/cli.py -- --upper upper.stl --lower lower.stl [--dicom-dir path] [--screws screws.json] [output.png]

Opciones de guía:
    --guide-mode full_arch|local   Modo de cobertura (default: full_arch)
    --shell-thickness <mm>         Espesor del shell (default: 3.0)
    --sleeve-height <mm>           Altura del sleeve guía (default: 5.0)
"""
import sys
import os

# Agregar src/ al path
sys.path.insert(0, os.path.dirname(__file__))

from loader import clear_scene, load_dual_arch
from camera import setup_occlusal_camera
from render import setup_lighting, setup_material, render_to_file


def parse_args(argv):
    """Parsea argumentos después de '--'."""
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []

    parsed = {
        'upper_arch': None,
        'lower_arch': None,
        'dicom_dir': None,
        'screws_json': None,
        'output_png': None,
        'output_guide_stl': None,
        'guide_mode': 'full_arch',
        'shell_thickness': 3.0,
        'sleeve_height': 5.0,
    }

    positional = []
    i = 0
    while i < len(args):
        if args[i] == '--upper' and i + 1 < len(args):
            parsed['upper_arch'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--lower' and i + 1 < len(args):
            parsed['lower_arch'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--dicom-dir' and i + 1 < len(args):
            parsed['dicom_dir'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--screws' and i + 1 < len(args):
            parsed['screws_json'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--output-guide' and i + 1 < len(args):
            parsed['output_guide_stl'] = os.path.abspath(args[i + 1])
            i += 2
        elif args[i] == '--guide-mode' and i + 1 < len(args):
            parsed['guide_mode'] = args[i + 1]
            i += 2
        elif args[i] == '--shell-thickness' and i + 1 < len(args):
            parsed['shell_thickness'] = float(args[i + 1])
            i += 2
        elif args[i] == '--sleeve-height' and i + 1 < len(args):
            parsed['sleeve_height'] = float(args[i + 1])
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if positional:
        parsed['output_png'] = os.path.abspath(positional[0])
    else:
        parsed['output_png'] = os.path.abspath("output/oclusal.png")

    return parsed


def main():
    parsed = parse_args(sys.argv)

    if not parsed['upper_arch'] or not parsed['lower_arch']:
        print("Uso: blender --background --python src/cli.py -- --upper <upper.stl> --lower <lower.stl> [opciones] [output.png]")
        print("  --upper <path>         Arco superior STL (requerido)")
        print("  --lower <path>         Arco inferior STL (requerido)")
        print("  --dicom-dir <path>     Directorio con serie DICOM (CBCT)")
        print("  --screws <json>        Posiciones de tornillos (JSON)")
        print("  --output-guide <path>  Exportar guía quirúrgica STL")
        print("  --guide-mode <mode>    Modo de cobertura: full_arch (default) o local")
        print("  --shell-thickness <n>  Espesor del shell en mm (default: 3.0)")
        print("  --sleeve-height <n>    Altura del sleeve guía en mm (default: 5.0)")
        sys.exit(1)

    output_png = parsed['output_png']

    for label, path in [('upper', parsed['upper_arch']), ('lower', parsed['lower_arch'])]:
        if not os.path.exists(path):
            print(f"Error: archivo no encontrado ({label}): {path}")
            sys.exit(1)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    print(f"Cargando arcos: superior={parsed['upper_arch']}, inferior={parsed['lower_arch']}")
    clear_scene()
    arches = load_dual_arch(parsed['upper_arch'], parsed['lower_arch'])
    upper_obj = arches['upper']
    print(f"Arcos cargados: {upper_obj.name}, {arches['lower'].name}")

    # CBCT (Phase 2)
    if parsed['dicom_dir']:
        _process_cbct(parsed['dicom_dir'])

    # Guide generation (Phase 3)
    guide_obj = None
    if parsed['screws_json']:
        guide_obj = _generate_guide(upper_obj, parsed['screws_json'], parsed['output_guide_stl'], parsed)

    print("Configurando cámara oclusal...")
    additional = [arches['lower']]
    if guide_obj:
        additional.append(guide_obj)
    setup_occlusal_camera(upper_obj, additional_objects=additional)

    print("Configurando iluminación y material...")
    setup_lighting()
    setup_material(upper_obj)
    setup_material(arches['lower'])

    print(f"Renderizando a: {output_png}")
    render_to_file(output_png)

    print("¡Listo!")


def _process_cbct(dicom_dir):
    """Carga volumen CBCT desde directorio DICOM."""
    from radiograph import load_dicom_series

    if not os.path.isdir(dicom_dir):
        print(f"Error: directorio DICOM no encontrado: {dicom_dir}")
        sys.exit(1)

    print(f"Cargando CBCT: {dicom_dir}")
    cbct_data = load_dicom_series(dicom_dir)
    print(f"CBCT: {cbct_data['depth']} slices, "
          f"{cbct_data['width']}x{cbct_data['height']} px, "
          f"spacing {cbct_data['spacing']} mm")


def _generate_guide(upper_obj, screws_json, output_guide_stl, parsed=None):
    """Genera guía quirúrgica a partir de posiciones de tornillos."""
    from guide import load_screw_positions, create_surgical_guide, export_guide_stl

    if not os.path.exists(screws_json):
        print(f"Error: archivo de tornillos no encontrado: {screws_json}")
        sys.exit(1)

    print(f"Cargando posiciones de tornillos: {screws_json}")
    screw_positions = load_screw_positions(screws_json)

    if not screw_positions:
        print("Advertencia: no hay posiciones de tornillos definidas, saltando guía")
        return None

    opts = parsed or {}
    print(f"Generando guía quirúrgica con {len(screw_positions)} tornillos...")
    result = create_surgical_guide(
        upper_obj, screw_positions,
        guide_mode=opts.get('guide_mode', 'full_arch'),
        shell_thickness=opts.get('shell_thickness', 3.0),
        sleeve_height=opts.get('sleeve_height', 5.0),
    )
    guide_obj = result['guide_obj']

    if output_guide_stl:
        os.makedirs(os.path.dirname(output_guide_stl), exist_ok=True)
        export_guide_stl(guide_obj, output_guide_stl)

    return guide_obj


if __name__ == "__main__":
    main()
