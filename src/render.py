"""Configuración de iluminación y renderizado."""
import bpy


def setup_lighting():
    """Configura iluminación básica con una sun lamp."""
    light_data = bpy.data.lights.new("SunLight", type='SUN')
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("SunLight", light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.rotation_euler = (0.5, 0.3, 0.2)
    return light_obj


def setup_material(obj):
    """Asigna material básico al objeto dental."""
    mat = bpy.data.materials.new("DentalMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.9, 0.85, 0.75, 1.0)  # Color hueso
    bsdf.inputs["Roughness"].default_value = 0.4
    obj.data.materials.append(mat)
    return mat


def render_to_file(output_path, resolution_x=1920, resolution_y=1080):
    """Renderiza la escena y guarda el resultado como imagen.

    Args:
        output_path: Ruta del archivo PNG de salida.
        resolution_x: Ancho en píxeles.
        resolution_y: Alto en píxeles.
    """
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.device = 'CPU'
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = output_path

    # Disable denoising (not available in distro Blender builds)
    scene.cycles.use_denoising = False

    # Fondo blanco
    scene.render.film_transparent = False
    bpy.context.scene.world = bpy.data.worlds.new("World")
    bpy.context.scene.world.use_nodes = True
    bg_node = bpy.context.scene.world.node_tree.nodes["Background"]
    bg_node.inputs["Color"].default_value = (1, 1, 1, 1)

    bpy.ops.render.render(write_still=True)
    print(f"Render guardado en: {output_path}")
