bl_info = {
    "name": "Reference Camera Setup",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Reference Photos",
    "description": "Quickly set up cameras with background images for reference photos",
    "category": "Camera",
}

import bpy
from bpy.types import (Panel, Operator)
from bpy.props import (StringProperty, BoolProperty, FloatProperty)

class REFCAM_OT_add_reference_camera(Operator):
    """Add a camera aligned to view with optional background image"""
    bl_idname = "refcam.add_reference_camera"
    bl_label = "Add Reference Camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Properties for additional features
    camera_name: StringProperty(
        name="Camera Name",
        default="RefCam",
        description="Name for the new camera"
    )
    
    lock_camera: BoolProperty(
        name="Lock Camera",
        default=True,
        description="Lock camera transforms after creation"
    )
    
    alpha: FloatProperty(
        name="Background Opacity",
        default=0.8,
        min=0.0,
        max=1.0,
        description="Opacity of the background image"
    )

    def ensure_collection_exists(self, context):
        """Ensure 'Reference Photos' collection exists, create if not"""
        if "Reference Photos" not in bpy.data.collections:
            ref_collection = bpy.data.collections.new("Reference Photos")
            context.scene.collection.children.link(ref_collection)
        return bpy.data.collections["Reference Photos"]

    def execute(self, context):
        # Get the reference collection
        ref_collection = self.ensure_collection_exists(context)
        
        # Create new camera
        camera_data = bpy.data.cameras.new(name=self.camera_name)
        camera_obj = bpy.data.objects.new(self.camera_name, camera_data)
        
        # Link camera to Reference Photos collection
        ref_collection.objects.link(camera_obj)
        
        # Set as active camera
        context.scene.camera = camera_obj
        
        # Align to current view
        view3d = context.space_data
        if view3d.type == 'VIEW_3D':
            camera_obj.matrix_world = view3d.region_3d.view_matrix.inverted()
        
        # Try to get selected image from file browser
        selected_image = None
        for area in context.screen.areas:
            if area.type == 'FILE_BROWSER':
                for file in area.spaces.active.params.selected_files:
                    try:
                        selected_image = bpy.data.images.load(file.path)
                        break
                    except:
                        self.report({'WARNING'}, "Could not load selected image")
        
        # Add background image if one was found
        if selected_image:
            bg = camera_data.background_images.new()
            bg.image = selected_image
            bg.alpha = self.alpha
        
        # Lock camera transforms if requested
        if self.lock_camera:
            camera_obj.lock_location = (True, True, True)
            camera_obj.lock_rotation = (True, True, True)
            camera_obj.lock_scale = (True, True, True)
        
        # Select the camera object
        bpy.ops.object.select_all(action='DESELECT')
        camera_obj.select_set(True)
        context.view_layer.objects.active = camera_obj
        
        self.report({'INFO'}, f"Created reference camera: {self.camera_name}")
        return {'FINISHED'}

class REFCAM_PT_main_panel(Panel):
    """Reference Camera UI Panel"""
    bl_label = "Reference Camera Setup"
    bl_idname = "REFCAM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Reference Photos'

    def draw(self, context):
        layout = self.layout
        
        # Main operator button
        row = layout.row()
        row.scale_y = 2.0  # Make button larger
        row.operator(REFCAM_OT_add_reference_camera.bl_idname, icon='CAMERA_DATA')
        
        # Settings
        box = layout.box()
        box.label(text="Settings:")
        box.prop(context.scene, "ref_cam_name")
        box.prop(context.scene, "ref_cam_lock")
        box.prop(context.scene, "ref_cam_alpha")

def register():
    bpy.types.Scene.ref_cam_name = StringProperty(
        name="Camera Name",
        default="RefCam",
        description="Base name for new reference cameras"
    )
    bpy.types.Scene.ref_cam_lock = BoolProperty(
        name="Lock Camera",
        default=True,
        description="Lock camera transforms after creation"
    )
    bpy.types.Scene.ref_cam_alpha = FloatProperty(
        name="Background Opacity",
        default=0.8,
        min=0.0,
        max=1.0,
        description="Opacity of the background image"
    )
    
    bpy.utils.register_class(REFCAM_OT_add_reference_camera)
    bpy.utils.register_class(REFCAM_PT_main_panel)

def unregister():
    del bpy.types.Scene.ref_cam_name
    del bpy.types.Scene.ref_cam_lock
    del bpy.types.Scene.ref_cam_alpha
    
    bpy.utils.unregister_class(REFCAM_OT_add_reference_camera)
    bpy.utils.unregister_class(REFCAM_PT_main_panel)

if __name__ == "__main__":
    register()
