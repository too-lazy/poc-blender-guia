"""Carga de modelos 3D (STL) en Blender."""
import bpy
import os


def clear_scene():
    """Elimina todos los objetos de la escena."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def load_stl(filepath):
    """Carga un archivo STL, lo centra en el origen y retorna el objeto.

    Args:
        filepath: Ruta al archivo STL.

    Returns:
        El objeto mesh importado.
    """
    bpy.ops.wm.stl_import(filepath=filepath)
    obj = bpy.context.selected_objects[0]

    # Centrar el objeto en el origen
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location = (0, 0, 0)

    return obj


def load_dual_arch(upper_path, lower_path):
    """Carga arco superior e inferior (iTero) y los posiciona juntos.

    iTero exporta STLs en mm con coordenadas ya en orientación dental estándar,
    por lo que ambos arcos comparten el mismo sistema de coordenadas y solo
    necesitan importarse sin re-centrar individualmente.

    Args:
        upper_path: Ruta al STL de arco superior (*_u.stl).
        lower_path: Ruta al STL de arco inferior (*_l_bite*.stl).

    Returns:
        dict con:
            - 'upper': objeto Blender de arco superior
            - 'lower': objeto Blender de arco inferior
            - 'center': coordenada del centro combinado (Vector)
    """
    for p in (upper_path, lower_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"STL no encontrado: {p}")

    # Importar superior
    bpy.ops.wm.stl_import(filepath=upper_path)
    upper = bpy.context.selected_objects[0]
    upper.name = "Arco_Superior"

    # Importar inferior
    bpy.ops.wm.stl_import(filepath=lower_path)
    lower = bpy.context.selected_objects[0]
    lower.name = "Arco_Inferior"

    # Centrar ambos modelos juntos en el origen usando el bounding box combinado
    _center_dual(upper, lower)

    print(f"Arco superior: {upper.name} ({_tri_count(upper)} triángulos)")
    print(f"Arco inferior: {lower.name} ({_tri_count(lower)} triángulos)")

    return {
        'upper': upper,
        'lower': lower,
        'center': upper.location.copy(),
    }


def _center_dual(upper, lower):
    """Centra ambos arcos juntos preservando su alineación relativa."""
    import mathutils

    # Calcular bounding box combinado en coordenadas mundo
    all_coords = []
    for obj in (upper, lower):
        for corner in obj.bound_box:
            all_coords.append(obj.matrix_world @ mathutils.Vector(corner))

    min_co = mathutils.Vector((
        min(c.x for c in all_coords),
        min(c.y for c in all_coords),
        min(c.z for c in all_coords),
    ))
    max_co = mathutils.Vector((
        max(c.x for c in all_coords),
        max(c.y for c in all_coords),
        max(c.z for c in all_coords),
    ))

    center = (min_co + max_co) / 2

    # Desplazar ambos objetos para centrar en origen
    for obj in (upper, lower):
        obj.location -= center


def _tri_count(obj):
    """Cuenta triángulos de un objeto mesh."""
    return len(obj.data.polygons)
