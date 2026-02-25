"""Carga de modelos 3D (STL) en Blender."""
import bpy


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
