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
    
    """Properties are handled at the Scene level"""

    def ensure_collection_exists(self, context):
        """Ensure 'Reference Photos' collection exists, create if not"""
        if "Reference Photos" not in bpy.data.collections:
            ref_collection = bpy.data.collections.new("Reference Photos")
            context.scene.collection.children.link(ref_collection)
        return bpy.data.collections["Reference Photos"]

    def execute(self, context):
        # Get the reference collection
        ref_collection = self.ensure_collection_exists(context)
        
        # Create new camera using Scene properties
        camera_data = bpy.data.cameras.new(name=context.scene.ref_cam_name)
        camera_obj = bpy.data.objects.new(context.scene.ref_cam_name, camera_data)
        
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
                params = area.spaces.active.params
                # Check if we have an active file browser with selected files
                if params and hasattr(params, 'filename') and params.filename:
                    try:
                        # Construct full path from directory and filename
                        filepath = params.directory.decode('utf-8') + params.filename
                        # Check if image is already loaded
                        existing_image = bpy.data.images.get(params.filename)
                        if existing_image:
                            selected_image = existing_image
                        else:
                            selected_image = bpy.data.images.load(filepath)
                        break
                    except Exception as e:
                        self.report({'WARNING'}, f"Could not load image: {str(e)}")
                        print(f"Error loading image: {str(e)}")  # Detailed error in console
        
        # Add background image if one was found
        if selected_image:
            # Enable background images
            camera_data.show_background_images = True
            
            # Create and configure background image
            bg = camera_data.background_images.new()
            bg.image = selected_image
            bg.alpha = context.scene.ref_cam_alpha
            bg.display_depth = 'FRONT'  # Set depth to Front
        
        # Lock camera transforms if requested
        if context.scene.ref_cam_lock:
            camera_obj.lock_location = (True, True, True)
            camera_obj.lock_rotation = (True, True, True)
            camera_obj.lock_scale = (True, True, True)
        
        # Select the camera object
        bpy.ops.object.select_all(action='DESELECT')
        camera_obj.select_set(True)
        context.view_layer.objects.active = camera_obj
        
        self.report({'INFO'}, f"Created reference camera: {context.scene.ref_cam_name}")
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
        
        # Show current image selection status
        box = layout.box()
        box.label(text="Image Status:")
        
        # Check if we have an active file browser with a selected image
        image_selected = False
        for area in context.screen.areas:
            if area.type == 'FILE_BROWSER':
                params = area.spaces.active.params
                if params and hasattr(params, 'filename') and params.filename:
                    box.label(text=f"Selected: {params.filename}", icon='IMAGE_DATA')
                    image_selected = True
                    break
        
        if not image_selected:
            box.label(text="No image selected in file browser", icon='ERROR')

def register():
    # Add a property to show the current image path
    bpy.types.Scene.ref_cam_image_path = StringProperty(
        name="Selected Image",
        default="",
        description="Currently selected image path",
        subtype='FILE_PATH'
    )
    
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
    del bpy.types.Scene.ref_cam_image_path
    del bpy.types.Scene.ref_cam_name
    del bpy.types.Scene.ref_cam_lock
    del bpy.types.Scene.ref_cam_alpha
    
    bpy.utils.unregister_class(REFCAM_OT_add_reference_camera)
    bpy.utils.unregister_class(REFCAM_PT_main_panel)

if __name__ == "__main__":
    register()
