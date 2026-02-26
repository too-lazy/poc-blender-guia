"""Overlay de radiografía como plano de referencia en escena Blender."""
import bpy
import os
import numpy as np


def create_radiograph_plane(radiograph_data, temp_image_path=None, name="RadioPlane"):
    """Crea un plano en la escena con la radiografía como textura.

    Args:
        radiograph_data: dict retornado por radiograph.load_radiograph.
        temp_image_path: ruta a imagen temporal para la textura. Si None, se genera automáticamente.
        name: nombre del objeto en Blender.

    Returns:
        El objeto plano con la textura aplicada.
    """
    width = radiograph_data['width']
    height = radiograph_data['height']
    aspect = width / height

    # Guardar imagen temporal para textura de Blender
    if temp_image_path is None:
        temp_image_path = os.path.join(os.path.dirname(__file__), '..', 'output', '_radio_texture.png')
        temp_image_path = os.path.abspath(temp_image_path)

    _save_texture(radiograph_data, temp_image_path)

    # Crear plano con aspecto correcto
    bpy.ops.mesh.primitive_plane_add(size=1)
    plane = bpy.context.active_object
    plane.name = name

    # Escalar para mantener aspect ratio (ancho = aspect, alto = 1)
    plane.scale = (aspect, 1.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)

    # Aplicar material con textura
    _apply_radiograph_material(plane, temp_image_path, name)

    return plane


def position_plane_below(plane, target_obj, offset_z=-0.5):
    """Posiciona el plano de referencia debajo del modelo dental.

    Args:
        plane: objeto plano con radiografía.
        target_obj: objeto dental 3D de referencia.
        offset_z: desplazamiento Z debajo del punto más bajo del modelo.
    """
    from mathutils import Vector
    bbox = [target_obj.matrix_world @ Vector(c) for c in target_obj.bound_box]

    center = sum(bbox, Vector()) / 8
    min_z = min(v.z for v in bbox)

    plane.location = (center.x, center.y, min_z + offset_z)


def scale_plane_to_model(plane, target_obj, margin=1.2):
    """Escala el plano para que cubra el tamaño del modelo dental.

    Args:
        plane: objeto plano con radiografía.
        target_obj: objeto dental 3D.
        margin: factor de margen (1.2 = 20% más grande).
    """
    model_width = target_obj.dimensions.x
    model_depth = target_obj.dimensions.y
    plane_width = plane.dimensions.x
    plane_height = plane.dimensions.y

    # Escalar para que el plano cubra el modelo
    scale_factor = max(model_width / plane_width, model_depth / plane_height) * margin
    plane.scale = (scale_factor, scale_factor, 1.0)
    bpy.ops.object.transform_apply(scale=True)


def set_plane_opacity(plane, alpha=0.7):
    """Ajusta la opacidad/transparencia del plano de referencia.

    Args:
        plane: objeto plano con material.
        alpha: valor de opacidad (0.0 = invisible, 1.0 = opaco).
    """
    if not plane.data.materials:
        return

    mat = plane.data.materials[0]
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else None
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Alpha"].default_value = alpha

    # Configurar transparencia en el material
    mat.use_backface_culling = False


def _apply_radiograph_material(plane, image_path, name="RadioMat"):
    """Aplica un material con textura de imagen al plano."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Limpiar nodos por defecto
    for node in nodes:
        nodes.remove(node)

    # Nodos: Image Texture → Principled BSDF → Material Output
    output_node = nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.0

    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.location = (-300, 0)
    tex_node.image = bpy.data.images.load(image_path)

    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    plane.data.materials.append(mat)


def _save_texture(radiograph_data, output_path):
    """Guarda la imagen como PNG para usarla como textura en Blender."""
    image = radiograph_data['image']
    image_uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        import cv2
        if len(image_uint8.shape) == 3 and image_uint8.shape[2] == 3:
            image_uint8 = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, image_uint8)
    except ImportError:
        from PIL import Image as PILImage
        if len(image_uint8.shape) == 2:
            pil_img = PILImage.fromarray(image_uint8, mode='L')
        else:
            pil_img = PILImage.fromarray(image_uint8)
        pil_img.save(output_path)
