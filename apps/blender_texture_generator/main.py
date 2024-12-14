bl_info = {
    "name": "AI Brush Texture Generator",
    "author": "Your Name",
    "version": (1, 1),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > AI Brush Gen",
    "description": "Generate brush textures using AI",
    "category": "Development",
}

import bpy
import os
import tempfile
import replicate
from bpy.props import StringProperty
from urllib.request import urlretrieve
from urllib.error import URLError

class BrushTextureGeneratorPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    api_token: StringProperty(
        name="Replicate API Token",
        description="Enter your Replicate API token",
        default="",
        subtype='PASSWORD'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_token")

class GenerateBrushTextureOperator(bpy.types.Operator):
    bl_idname = "texture.generate_brush_texture"
    bl_label = "Generate Brush Texture"
    bl_options = {'REGISTER', 'UNDO'}

    texture_prompt: StringProperty(
        name="Texture Type",
        description="Enter texture type (e.g., brick, stone, wood)",
        default="brick"
    )

    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        api_token = preferences.api_token

        if not api_token:
            self.report({'ERROR'}, "Please set your Replicate API token in addon preferences")
            return {'CANCELLED'}

        if not self.texture_prompt.strip():
            self.report({'ERROR'}, "Texture prompt cannot be empty")
            return {'CANCELLED'}

        os.environ['REPLICATE_API_TOKEN'] = api_token

        # Generate the complete prompt
        base_prompt = ("Studio overhead shot of {texture} surface in perfect 8K monochrome, "
                       "captured with professional ring light creating circular gradient falloff. "
                       "Central 70% shows crystal-clear {texture} detail with 10x10 visible pattern elements. "
                       "Outer edges fade to pure black through professional light falloff. "
                       "Museum-grade material photography, extreme detail preservation")
        prompt = base_prompt.format(texture=self.texture_prompt)

        try:
            # Run the model
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "go_fast": True,
                    "megapixels": "1",
                    "num_outputs": 1,
                    "aspect_ratio": "1:1",
                    "output_format": "webp",
                    "output_quality": 80,
                    "num_inference_steps": 4
                }
            )

            if not output or not isinstance(output, list):
                self.report({'ERROR'}, "No valid output received from API")
                return {'CANCELLED'}

            # Get the image URL from the output
            image_url = output[0]

            # Create a temporary file to store the image
            temp_dir = tempfile.gettempdir()
            temp_image_path = os.path.join(temp_dir, f"brush_texture_{self.texture_prompt}.webp")

            try:
                # Download the image
                urlretrieve(image_url, temp_image_path)
            except URLError as e:
                self.report({'ERROR'}, f"Failed to download image: {e.reason}")
                return {'CANCELLED'}

            # Create a new texture
            texture_name = f"BrushTex_{self.texture_prompt}"
            try:
                img = bpy.data.images.load(temp_image_path)
                tex = bpy.data.textures.new(name=texture_name, type='IMAGE')
                tex.image = img
            except Exception as e:
                self.report({'ERROR'}, f"Failed to create texture in Blender: {str(e)}")
                return {'CANCELLED'}

            self.report({'INFO'}, f"Generated texture: {texture_name}")
            return {'FINISHED'}

        except replicate.exceptions.ReplicateException as e:
            self.report({'ERROR'}, f"API Error: {str(e)}")
            return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {str(e)}")
            return {'CANCELLED'}

class VIEW3D_PT_brush_texture_generator(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AI Brush Gen'
    bl_label = "Brush Texture Generator"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "texture_prompt")
        layout.operator("texture.generate_brush_texture")

def register():
    bpy.types.Scene.texture_prompt = StringProperty(
        name="Texture Type",
        description="Enter texture type (e.g., brick, stone, wood)",
        default="brick"
    )

    bpy.utils.register_class(BrushTextureGeneratorPreferences)
    bpy.utils.register_class(GenerateBrushTextureOperator)
    bpy.utils.register_class(VIEW3D_PT_brush_texture_generator)

def unregister():
    del bpy.types.Scene.texture_prompt

    bpy.utils.unregister_class(VIEW3D_PT_brush_texture_generator)
    bpy.utils.unregister_class(GenerateBrushTextureOperator)
    bpy.utils.unregister_class(BrushTextureGeneratorPreferences)

if __name__ == "__main__":
    register()
