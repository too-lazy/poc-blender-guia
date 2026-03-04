"""Generación de guía quirúrgica para tornillos de anclaje ortodóntico."""
import bpy
import bmesh
import json
import math
from mathutils import Vector, Matrix


# Defaults para mini-tornillos ortodónticos
DEFAULT_GUIDE_MODE = "full_arch"        # "full_arch" o "local"
DEFAULT_SHELL_THICKNESS = 3.0           # mm — espesor de la guía (3mm para rigidez)
DEFAULT_CYLINDER_DIAMETER = 1.6         # mm — diámetro del canal guía (tornillo ~1.4mm + 0.1mm clearance)
DEFAULT_CYLINDER_DEPTH = 8.0            # mm — profundidad del canal
DEFAULT_GUIDE_MARGIN = 25.0             # mm — margen alrededor de los tornillos (solo modo local)
DEFAULT_SHRINKAGE_COMPENSATION = 1.005  # 0.5% compensación por contracción de resina
DEFAULT_FIT_GAP = 0.08                  # mm — gap entre guía y modelo dental (50-100µm)
DEFAULT_SLEEVE_HEIGHT = 5.0             # mm — altura del sleeve sobre la superficie de la guía
DEFAULT_SLEEVE_OUTER_DIAMETER = 3.5     # mm — diámetro exterior del sleeve guía
DEFAULT_DECIMATE_RATIO = 0.3            # fracción de caras a conservar tras decimación


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
                          shrinkage_comp=DEFAULT_SHRINKAGE_COMPENSATION,
                          guide_mode=DEFAULT_GUIDE_MODE,
                          sleeve_height=DEFAULT_SLEEVE_HEIGHT,
                          sleeve_outer_diameter=DEFAULT_SLEEVE_OUTER_DIAMETER,
                          decimate_ratio=DEFAULT_DECIMATE_RATIO):
    """Genera la guía quirúrgica a partir del arco dental y posiciones de tornillos.

    Args:
        arch_obj: Objeto Blender del arco dental (mesh).
        screw_positions: Lista de dicts con x, y, z, angle_x, angle_y, angle_z.
        shell_thickness: Espesor de la guía en mm.
        cylinder_diameter: Diámetro interior del canal guía en mm.
        cylinder_depth: Profundidad del canal guía en mm.
        guide_margin: Margen de recorte en modo "local" (mm).
        fit_gap: Gap entre guía y dientes en mm.
        shrinkage_comp: Factor de compensación por contracción de resina.
        guide_mode: "full_arch" (cubre todo el arco) o "local" (solo zona tornillos).
        sleeve_height: Altura de los sleeves guía sobre la superficie en mm.
        sleeve_outer_diameter: Diámetro exterior de los sleeves en mm.
        decimate_ratio: Fracción de caras a conservar tras decimación (0.3 = 30%).

    Returns:
        Dict con 'guide_obj' (objeto Blender de la guía).
    """
    print(f"Generando guía: {len(screw_positions)} tornillos, modo={guide_mode}, "
          f"shell={shell_thickness}mm, Ø canal={cylinder_diameter}mm")

    # 1. Duplicar el arco dental como base de la guía
    guide_obj = _duplicate_mesh(arch_obj, "GuiaQuirurgica")

    # 2. Aplicar gap de ajuste: expandir la superficie outward por fit_gap
    _apply_shrink_fatten(guide_obj, fit_gap)

    # 3. Aplicar Solidify para crear el shell de la guía (offset=1 = hacia afuera)
    _apply_solidify(guide_obj, shell_thickness, offset=1)
    _apply_modifier(guide_obj, "GuideShell")

    # 4. Recortar según modo:
    #    - "full_arch": conservar todo el arco (no recortar)
    #    - "local": recortar a zona de tornillos + suavizar bordes
    if guide_mode == "local" and guide_margin > 0 and screw_positions:
        _trim_to_screw_region(guide_obj, screw_positions, guide_margin)
        _smooth_boundary(guide_obj)
    else:
        print(f"  Modo full_arch: conservando arco completo")

    # 5. Crear sleeves y canales guía en cada posición de tornillo
    for i, pos in enumerate(screw_positions):
        # a) Unir sleeve (tubo exterior) a la guía
        sleeve = _create_guide_sleeve(
            f"Sleeve_{i+1}", pos,
            inner_diameter=cylinder_diameter,
            outer_diameter=sleeve_outer_diameter,
            height=sleeve_height,
            shell_thickness=shell_thickness,
        )
        _boolean_union(guide_obj, sleeve)

        # b) Sustraer canal interior a través del sleeve y la guía
        channel = _create_guide_cylinder(
            f"Canal_{i+1}", pos,
            diameter=cylinder_diameter,
            depth=cylinder_depth + sleeve_height,
        )
        _boolean_subtract(guide_obj, channel)
        print(f"  Sleeve+canal {i+1} en ({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f})")

    # 6. Limpiar mesh (remover dobles, rellenar agujeros, recalcular normales)
    _cleanup_mesh(guide_obj)

    # 7. Decimación: reducir polígonos protegiendo la geometría de los canales
    if decimate_ratio < 1.0:
        _decimate_mesh(guide_obj, screw_positions, decimate_ratio)

    # 8. Aplicar compensación por contracción de resina
    if shrinkage_comp != 1.0:
        guide_obj.scale *= shrinkage_comp
        bpy.context.view_layer.objects.active = guide_obj
        bpy.ops.object.transform_apply(scale=True)
        print(f"  Compensación contracción: {(shrinkage_comp - 1) * 100:.1f}%")

    # 9. Aplicar material de guía
    _apply_guide_material(guide_obj)

    print(f"Guía generada: {len(guide_obj.data.polygons)} polígonos")
    return {'guide_obj': guide_obj}


def export_guide_stl(guide_obj, output_path):
    """Exporta la guía quirúrgica como STL.

    Args:
        guide_obj: Objeto Blender de la guía.
        output_path: Ruta del archivo STL de salida.
    """
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


def _apply_shrink_fatten(obj, distance):
    """Expande los vértices del mesh a lo largo de sus normales por 'distance' mm."""
    bpy.context.view_layer.objects.active = obj
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.co += v.normal * distance
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


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
        # Si no encuentra por nombre, aplica el primero
        for mod in obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=mod.name)
            return
    else:
        while obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=obj.modifiers[0].name)


def _trim_to_screw_region(guide_obj, screw_positions, margin):
    """Recorta la guía a la zona de tornillos (modo local).

    Elimina vértices cuya distancia mínima a cualquier tornillo exceda el margen.
    Rellena los agujeros resultantes para mantener el mesh watertight.
    """
    screw_vectors = [Vector((p['x'], p['y'], p['z'])) for p in screw_positions]

    bpy.context.view_layer.objects.active = guide_obj
    bm = bmesh.new()
    bm.from_mesh(guide_obj.data)

    world_matrix = guide_obj.matrix_world
    verts_to_remove = []
    for v in bm.verts:
        world_co = world_matrix @ v.co
        min_dist = min((world_co - s).length for s in screw_vectors)
        if min_dist > margin:
            verts_to_remove.append(v)

    if verts_to_remove and len(verts_to_remove) < len(bm.verts):
        bmesh.ops.delete(bm, geom=verts_to_remove, context='VERTS')
        print(f"  Recorte: eliminados {len(verts_to_remove)} vértices fuera de zona")

        bm.edges.ensure_lookup_table()
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        if boundary_edges:
            bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=200)
            print(f"  Cerrado: rellenados agujeros ({len(boundary_edges)} bordes frontera)")

        bm.to_mesh(guide_obj.data)
        guide_obj.data.update()

    bm.free()


def _smooth_boundary(guide_obj, iterations=8, factor=0.5):
    """Suaviza los vértices cercanos al borde de recorte con Laplacian Smooth.

    Crea un vertex group para los vértices de borde y sus vecinos (3 anillos),
    aplica el modificador LAPLACIANSMOOTH restringido a ese grupo, y limpia.
    """
    bpy.context.view_layer.objects.active = guide_obj

    bm = bmesh.new()
    bm.from_mesh(guide_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Encontrar vértices en el borde
    boundary_indices = set()
    for e in bm.edges:
        if e.is_boundary:
            boundary_indices.add(e.verts[0].index)
            boundary_indices.add(e.verts[1].index)

    if not boundary_indices:
        bm.free()
        return

    # Expandir 3 anillos para suavizado gradual
    expand_indices = set(boundary_indices)
    for _ in range(3):
        new_verts = set()
        for vi in expand_indices:
            v = bm.verts[vi]
            for e in v.link_edges:
                new_verts.add(e.other_vert(v).index)
        expand_indices.update(new_verts)

    bm.free()

    # Crear vertex group con pesos
    vg = guide_obj.vertex_groups.new(name="BoundarySmooth")
    for vi in expand_indices:
        weight = 1.0 if vi in boundary_indices else 0.4
        vg.add([vi], weight, 'REPLACE')

    # Aplicar Laplacian Smooth restringido al grupo
    mod = guide_obj.modifiers.new(name="BoundarySmooth", type='LAPLACIANSMOOTH')
    mod.iterations = iterations
    mod.lambda_factor = factor
    mod.lambda_border = 0.0
    mod.vertex_group = "BoundarySmooth"

    bpy.ops.object.modifier_apply(modifier=mod.name)
    guide_obj.vertex_groups.remove(vg)

    print(f"  Borde suavizado: {len(boundary_indices)} verts frontera, "
          f"{len(expand_indices)} afectados, {iterations} iteraciones")


def _create_guide_sleeve(name, position, inner_diameter, outer_diameter,
                         height, shell_thickness):
    """Crea el sleeve exterior del canal guía (tubo protruente sobre la guía).

    El sleeve es un cilindro sólido que se unirá con boolean UNION a la guía.
    Tras la unión, se sustrae el canal interior para crear el tubo hueco.

    Args:
        inner_diameter: diámetro interior = diámetro del canal de la broca
        outer_diameter: diámetro exterior del sleeve
        height: cuánto protruye el sleeve sobre la superficie de la guía
        shell_thickness: espesor de la guía (el sleeve se ancla en ella)
    """
    anchor_depth = shell_thickness + 1.0  # 1mm extra de anclaje dentro de la guía
    total_length = height + anchor_depth

    loc = (position['x'], position['y'], position['z'])

    bpy.ops.mesh.primitive_cylinder_add(
        radius=outer_diameter / 2.0,
        depth=total_length,
        vertices=32,
        location=loc
    )
    sleeve = bpy.context.active_object
    sleeve.name = name

    angle_x = math.radians(position.get('angle_x', 0))
    angle_y = math.radians(position.get('angle_y', 0))
    angle_z = math.radians(position.get('angle_z', 0))
    sleeve.rotation_euler = (angle_x, angle_y, angle_z)

    # Desplazar a lo largo del eje de inserción para que protruya height mm
    rot_matrix = sleeve.rotation_euler.to_matrix()
    offset = rot_matrix @ Vector((0, 0, (height - anchor_depth) / 2.0))
    sleeve.location = Vector(loc) + offset

    bpy.ops.object.transform_apply(rotation=True, location=True)

    return sleeve


def _create_guide_cylinder(name, position, diameter, depth):
    """Crea un cilindro guía (canal de broca) en la posición del tornillo."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2.0,
        depth=depth,
        vertices=32,
        location=(position['x'], position['y'], position['z'])
    )
    cylinder = bpy.context.active_object
    cylinder.name = name

    angle_x = math.radians(position.get('angle_x', 0))
    angle_y = math.radians(position.get('angle_y', 0))
    angle_z = math.radians(position.get('angle_z', 0))
    cylinder.rotation_euler = (angle_x, angle_y, angle_z)

    bpy.ops.object.transform_apply(rotation=True)

    return cylinder


def _boolean_union(target_obj, tool_obj):
    """Aplica operación booleana de unión (union).

    Usa solver FLOAT que es más robusto con meshes no-manifold (STLs de escaneo dental).
    """
    bpy.context.view_layer.objects.active = target_obj
    mod = target_obj.modifiers.new(name="BoolUnion", type='BOOLEAN')
    mod.operation = 'UNION'
    mod.object = tool_obj
    mod.solver = 'FLOAT'

    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool_obj, do_unlink=True)


def _boolean_subtract(target_obj, tool_obj):
    """Aplica operación booleana de resta (difference).

    Usa solver FLOAT que es más robusto con meshes no-manifold (STLs de escaneo dental).
    """
    bpy.context.view_layer.objects.active = target_obj
    mod = target_obj.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = tool_obj
    mod.solver = 'FLOAT'

    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool_obj, do_unlink=True)


def _cleanup_mesh(obj):
    """Limpia el mesh: merge doubles, fill holes, recalcular normales.

    Ensures the output is watertight (manifold) for 3D printing.
    """
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.01)

    bpy.ops.mesh.select_non_manifold(extend=False)
    bpy.ops.mesh.fill_holes(sides=200)

    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    print(f"  Mesh cleanup: {len(obj.data.polygons)} polígonos, "
          f"{boundary} boundary edges, {non_manifold} non-manifold edges")
    bm.free()

    obj.select_set(False)


def _decimate_mesh(obj, screw_positions, target_ratio=0.3, protect_radius=5.0):
    """Reduce el número de polígonos preservando la geometría de los canales.

    Crea un vertex group para proteger los vértices cercanos a los tornillos
    (canales de broca) y aplica DECIMATE solo al resto de la guía.

    Args:
        obj: Objeto Blender de la guía.
        screw_positions: Lista de posiciones de tornillos para proteger.
        target_ratio: Fracción de caras a conservar (0.3 = conservar 30%).
        protect_radius: Radio de protección alrededor de cada tornillo en mm.
    """
    initial_polys = len(obj.data.polygons)

    bpy.context.view_layer.objects.active = obj

    # Vertex group para proteger canales
    vg = obj.vertex_groups.new(name="ChannelProtect")
    screw_vectors = [Vector((p['x'], p['y'], p['z'])) for p in screw_positions]

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    protect_indices = []
    for v in bm.verts:
        world_co = obj.matrix_world @ v.co
        min_dist = min((world_co - s).length for s in screw_vectors)
        if min_dist < protect_radius:
            protect_indices.append(v.index)

    bm.free()

    if protect_indices:
        vg.add(protect_indices, 1.0, 'REPLACE')

    mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target_ratio
    if protect_indices:
        mod.vertex_group = "ChannelProtect"
        mod.invert_vertex_group = True  # decimar TODO EXCEPTO los canales

    bpy.ops.object.modifier_apply(modifier=mod.name)

    # El modifier_apply puede desvincularse del vertex group — intentar eliminar por nombre
    vg_name = vg.name
    if vg_name in obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups[vg_name])

    final_polys = len(obj.data.polygons)
    print(f"  Decimación: {initial_polys} → {final_polys} polígonos "
          f"({final_polys/initial_polys*100:.0f}% conservado)")


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
