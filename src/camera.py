"""Configuración de cámara para vista oclusal."""
import bpy
from mathutils import Vector


def setup_occlusal_camera(target_obj, distance=None, ortho_scale=None, additional_objects=None):
    """Posiciona una cámara ortográfica mirando hacia abajo (vista oclusal).

    Args:
        target_obj: Objeto principal sobre el cual centrar la cámara.
        distance: Distancia de la cámara al objeto. Si None, se calcula automáticamente.
        ortho_scale: Escala ortográfica. Si None, se calcula automáticamente.
        additional_objects: Lista de objetos adicionales a incluir en el encuadre.

    Returns:
        El objeto cámara.
    """
    # Calcular bounding box combinado de todos los objetos
    all_objects = [target_obj] + (additional_objects or [])
    all_corners = []
    for obj in all_objects:
        all_corners.extend([obj.matrix_world @ Vector(corner) for corner in obj.bound_box])

    center = sum(all_corners, Vector()) / len(all_corners)

    min_co = Vector((min(c.x for c in all_corners), min(c.y for c in all_corners), min(c.z for c in all_corners)))
    max_co = Vector((max(c.x for c in all_corners), max(c.y for c in all_corners), max(c.z for c in all_corners)))
    dimensions = max_co - min_co

    # Calcular distancia automática: bien por encima del punto más alto
    if distance is None:
        distance = max(dimensions.x, dimensions.y, dimensions.z) * 1.5

    # Crear o reusar cámara
    cam_data = bpy.data.cameras.new("OcclusalCam")
    cam_data.type = 'ORTHO'
    # Use the larger dimension (X or Y) plus margin; portrait render will show full arch
    cam_data.ortho_scale = ortho_scale or max(dimensions.x, dimensions.y) * 1.15
    cam_data.clip_end = distance * 4

    cam_obj = bpy.data.objects.new("OcclusalCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Posicionar: arriba del objeto, mirando hacia abajo (-Z)
    cam_obj.location = (center.x, center.y, center.z + distance)
    cam_obj.rotation_euler = (0, 0, 0)  # Mirando hacia -Z por defecto en ortho

    bpy.context.scene.camera = cam_obj
    return cam_obj
