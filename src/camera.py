"""Configuración de cámara para vista oclusal."""
import bpy
from mathutils import Vector


def setup_occlusal_camera(target_obj, distance=0.3, ortho_scale=None):
    """Posiciona una cámara ortográfica mirando hacia abajo (vista oclusal).

    Args:
        target_obj: Objeto sobre el cual centrar la cámara.
        distance: Distancia de la cámara al objeto (metros).
        ortho_scale: Escala ortográfica. Si None, se calcula automáticamente.

    Returns:
        El objeto cámara.
    """
    # Calcular bounding box del objeto
    bbox = [target_obj.matrix_world @ Vector(corner) for corner in target_obj.bound_box]
    center = sum(bbox, Vector()) / 8
    dimensions = target_obj.dimensions

    # Crear o reusar cámara
    cam_data = bpy.data.cameras.new("OcclusalCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale or max(dimensions.x, dimensions.y) * 1.2

    cam_obj = bpy.data.objects.new("OcclusalCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Posicionar: arriba del objeto, mirando hacia abajo (-Z)
    cam_obj.location = (center.x, center.y, center.z + distance)
    cam_obj.rotation_euler = (0, 0, 0)  # Mirando hacia -Z por defecto en ortho

    bpy.context.scene.camera = cam_obj
    return cam_obj
