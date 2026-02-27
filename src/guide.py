"""Generación de guía quirúrgica para tornillos de anclaje ortodóntico."""
import bpy
import bmesh
import json
import math
from mathutils import Vector, Matrix


# Defaults para mini-tornillos ortodónticos
DEFAULT_SHELL_THICKNESS = 2.5       # mm — espesor de la guía
DEFAULT_CYLINDER_DIAMETER = 1.6     # mm — diámetro del canal guía (tornillo ~1.4mm + 0.1mm clearance)
DEFAULT_CYLINDER_DEPTH = 8.0        # mm — profundidad del canal
DEFAULT_GUIDE_MARGIN = 15.0         # mm — margen alrededor de los tornillos
DEFAULT_SHRINKAGE_COMPENSATION = 1.005  # 0.5% compensación por contracción de resina
DEFAULT_FIT_GAP = 0.08              # mm — gap entre guía y modelo dental (50-100µm)


def load_screw_positions(json_path):
    """Carga posiciones de tornillos desde archivo JSON.

    Formato esperado: [{"x": float, "y": float, "z": float,
                        "angle_x": float, "angle_y": float, "angle_z": float}, ...]
    Ángulos en grados. Si no se especifican ángulos, se usa dirección perpendicular a la superficie.
    """
    with open(json_path, 'r') as f:
        positions = json.load(f)

    validated = []
    for i, pos in enumerate(positions):
        entry = {
            'x': float(pos['x']),
            'y': float(pos['y']),
            'z': float(pos['z']),
            'angle_x': float(pos.get('angle_x', 0)),
            'angle_y': float(pos.get('angle_y', 0)),
            'angle_z': float(pos.get('angle_z', 0)),
        }
        validated.append(entry)
        print(f"  Tornillo {i+1}: ({entry['x']:.2f}, {entry['y']:.2f}, {entry['z']:.2f})")

    return validated


def create_surgical_guide(arch_obj, screw_positions,
                          shell_thickness=DEFAULT_SHELL_THICKNESS,
                          cylinder_diameter=DEFAULT_CYLINDER_DIAMETER,
                          cylinder_depth=DEFAULT_CYLINDER_DEPTH,
                          guide_margin=DEFAULT_GUIDE_MARGIN,
                          fit_gap=DEFAULT_FIT_GAP,
                          shrinkage_comp=DEFAULT_SHRINKAGE_COMPENSATION):
    """Genera la guía quirúrgica a partir del arco dental y posiciones de tornillos.

    Args:
        arch_obj: Objeto Blender del arco dental (mesh).
        screw_positions: Lista de dicts con x, y, z, angle_x, angle_y, angle_z.
        shell_thickness: Espesor de la guía en mm.
        cylinder_diameter: Diámetro interior del canal guía en mm.
        cylinder_depth: Profundidad del canal guía en mm.
        fit_gap: Gap entre guía y dientes en mm.
        shrinkage_comp: Factor de compensación por contracción de resina.

    Returns:
        Dict con 'guide_obj' (objeto Blender de la guía).
    """
    print(f"Generando guía: {len(screw_positions)} tornillos, "
          f"shell={shell_thickness}mm, Ø canal={cylinder_diameter}mm")

    # 1. Duplicar el arco dental como base de la guía
    guide_obj = _duplicate_mesh(arch_obj, "GuiaQuirurgica")

    # 2. Aplicar gap de ajuste (offset negativo pequeño para que la guía no pegue)
    _apply_solidify(guide_obj, fit_gap, offset=-1)
    _apply_modifier(guide_obj, "FitGap")

    # 3. Aplicar Solidify para crear el shell de la guía (offset hacia afuera)
    _apply_solidify(guide_obj, shell_thickness, offset=-1)
    _apply_modifier(guide_obj, "GuideShell")

    # 4. Recortar la guía para cubrir solo la zona de los tornillos
    if guide_margin > 0 and screw_positions:
        _trim_to_screw_region(guide_obj, screw_positions, guide_margin)

    # 5. Crear canales guía (cilindros) en cada posición de tornillo
    for i, pos in enumerate(screw_positions):
        cylinder = _create_guide_cylinder(
            f"Canal_{i+1}", pos,
            diameter=cylinder_diameter,
            depth=cylinder_depth
        )
        _boolean_subtract(guide_obj, cylinder)
        print(f"  Canal {i+1} creado en ({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f})")

    # 6. Limpiar mesh (remover dobles, recalcular normales)
    _cleanup_mesh(guide_obj)

    # 7. Aplicar compensación por contracción de resina
    if shrinkage_comp != 1.0:
        guide_obj.scale *= shrinkage_comp
        bpy.context.view_layer.objects.active = guide_obj
        bpy.ops.object.transform_apply(scale=True)
        print(f"  Compensación contracción: {(shrinkage_comp - 1) * 100:.1f}%")

    # 8. Aplicar material de guía
    _apply_guide_material(guide_obj)

    print(f"Guía generada: {len(guide_obj.data.polygons)} polígonos")
    return {'guide_obj': guide_obj}


def export_guide_stl(guide_obj, output_path):
    """Exporta la guía quirúrgica como STL.

    Args:
        guide_obj: Objeto Blender de la guía.
        output_path: Ruta del archivo STL de salida.
    """
    # Deseleccionar todo, seleccionar solo la guía
    bpy.ops.object.select_all(action='DESELECT')
    guide_obj.select_set(True)
    bpy.context.view_layer.objects.active = guide_obj

    bpy.ops.wm.stl_export(
        filepath=output_path,
        export_selected_objects=True,
        ascii_format=False
    )
    print(f"Guía exportada: {output_path}")


# --- Funciones internas ---

def _duplicate_mesh(obj, name):
    """Duplica un objeto mesh."""
    mesh_copy = obj.data.copy()
    new_obj = bpy.data.objects.new(name, mesh_copy)
    bpy.context.collection.objects.link(new_obj)
    new_obj.matrix_world = obj.matrix_world.copy()
    return new_obj


def _apply_solidify(obj, thickness, offset=-1):
    """Aplica modificador Solidify al objeto."""
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    mod.use_quality_normals = True


def _apply_modifier(obj, mod_name=None):
    """Aplica un modificador específico o todos los modificadores del objeto."""
    bpy.context.view_layer.objects.active = obj
    if mod_name:
        for mod in obj.modifiers:
            if mod.name == mod_name or mod.type == mod_name:
                bpy.ops.object.modifier_apply(modifier=mod.name)
                return
        # If exact name not found, apply first Solidify
        for mod in obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=mod.name)
            return
    else:
        while obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=obj.modifiers[0].name)


def _trim_to_screw_region(guide_obj, screw_positions, margin):
    """Recorta la guía para cubrir solo la región alrededor de los tornillos."""
    # Calcular bounding box de los tornillos + margen
    xs = [p['x'] for p in screw_positions]
    ys = [p['y'] for p in screw_positions]
    zs = [p['z'] for p in screw_positions]

    min_bound = Vector((min(xs) - margin, min(ys) - margin, min(zs) - margin))
    max_bound = Vector((max(xs) + margin, max(ys) + margin, max(zs) + margin))

    # Usar bmesh para eliminar vértices fuera de la región
    bpy.context.view_layer.objects.active = guide_obj
    bm = bmesh.new()
    bm.from_mesh(guide_obj.data)

    world_matrix = guide_obj.matrix_world
    verts_to_remove = []
    for v in bm.verts:
        world_co = world_matrix @ v.co
        if (world_co.x < min_bound.x or world_co.x > max_bound.x or
            world_co.y < min_bound.y or world_co.y > max_bound.y or
            world_co.z < min_bound.z or world_co.z > max_bound.z):
            verts_to_remove.append(v)

    if verts_to_remove and len(verts_to_remove) < len(bm.verts):
        bmesh.ops.delete(bm, geom=verts_to_remove, context='VERTS')
        bm.to_mesh(guide_obj.data)
        guide_obj.data.update()
        print(f"  Recorte: eliminados {len(verts_to_remove)} vértices fuera de zona")

    bm.free()


def _create_guide_cylinder(name, position, diameter, depth):
    """Crea un cilindro guía en la posición del tornillo."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2.0,
        depth=depth,
        vertices=32,
        location=(position['x'], position['y'], position['z'])
    )
    cylinder = bpy.context.active_object
    cylinder.name = name

    # Aplicar rotación según ángulos del tornillo
    angle_x = math.radians(position.get('angle_x', 0))
    angle_y = math.radians(position.get('angle_y', 0))
    angle_z = math.radians(position.get('angle_z', 0))
    cylinder.rotation_euler = (angle_x, angle_y, angle_z)

    # Aplicar transformaciones
    bpy.ops.object.transform_apply(rotation=True)

    return cylinder


def _boolean_subtract(target_obj, tool_obj):
    """Aplica operación booleana de resta (difference)."""
    bpy.context.view_layer.objects.active = target_obj
    mod = target_obj.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = tool_obj
    mod.solver = 'EXACT'

    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Eliminar el cilindro herramienta
    bpy.data.objects.remove(tool_obj, do_unlink=True)


def _cleanup_mesh(obj):
    """Limpia el mesh: merge doubles, recalcular normales."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.01)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    obj.select_set(False)


def _apply_guide_material(obj):
    """Aplica material semitransparente azul para visualización de la guía."""
    mat = bpy.data.materials.new("GuideMaterial")
    mat.use_nodes = True
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None

    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.2, 0.5, 0.9, 1.0)  # Azul
    bsdf.inputs["Alpha"].default_value = 0.7  # Semitransparente
    bsdf.inputs["Roughness"].default_value = 0.1  # Superficie lisa (resina)

    obj.data.materials.clear()
    obj.data.materials.append(mat)
