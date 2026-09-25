bl_info = {
    "name": "Origin to Mouse Pointer",
    "author": "Unlim8ted Studios",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Object Mode > U",
    "description": "Press U to set selected object origins to the 3D point under the mouse pointer",
    "category": "Object",
}

import bpy
from bpy_extras import view3d_utils


addon_keymaps = []


def get_mouse_world_position(context, event):
    """Return a world-space point corresponding to the mouse pointer."""
    region = context.region
    rv3d = context.region_data

    if region is None or rv3d is None:
        return None

    mouse = (event.mouse_region_x, event.mouse_region_y)

    # Build a ray through the actual 2D mouse pointer.
    ray_origin = view3d_utils.region_2d_to_origin_3d(
        region,
        rv3d,
        mouse,
    )

    ray_direction = view3d_utils.region_2d_to_vector_3d(
        region,
        rv3d,
        mouse,
    ).normalized()

    # Prefer the actual visible surface under the pointer.
    depsgraph = context.evaluated_depsgraph_get()

    hit, location, normal, face_index, hit_object, matrix = context.scene.ray_cast(
        depsgraph,
        ray_origin,
        ray_direction,
    )

    if hit:
        return location.copy()

    # If the pointer is over empty space, there is no unique 3D point.
    # Project the pointer onto the depth of the active object's origin.
    # The 3D Cursor is used only as a fallback depth reference if somehow
    # there is no active object.
    active = context.view_layer.objects.active

    if active is not None:
        depth_reference = active.matrix_world.translation.copy()
    else:
        depth_reference = context.scene.cursor.location.copy()

    return view3d_utils.region_2d_to_location_3d(
        region,
        rv3d,
        mouse,
        depth_reference,
    )


class OBJECT_OT_origin_to_mouse_pointer(bpy.types.Operator):
    """Set selected object origins to the point under the mouse pointer"""
    bl_idname = "object.origin_to_mouse_pointer"
    bl_label = "Origin to Mouse Pointer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == 'VIEW_3D'
            and context.mode == 'OBJECT'
            and len(context.selected_objects) > 0
        )

    def invoke(self, context, event):
        target = get_mouse_world_position(context, event)

        if target is None:
            self.report({'ERROR'}, "Could not determine a 3D mouse position")
            return {'CANCELLED'}

        scene = context.scene
        original_cursor = scene.cursor.location.copy()
        original_active = context.view_layer.objects.active
        original_selection = list(context.selected_objects)

        try:
            # Blender's origin_set operator accepts the 3D Cursor as an
            # arbitrary world-space origin target. We use it only internally,
            # then immediately restore it so the user's cursor does not move.
            scene.cursor.location = target

            bpy.ops.object.origin_set(
                type='ORIGIN_CURSOR',
                center='MEDIAN',
            )

        except RuntimeError as exc:
            self.report({'ERROR'}, f"Unable to set origin: {exc}")
            return {'CANCELLED'}

        finally:
            scene.cursor.location = original_cursor

            # Keep the user's selection and active object exactly as they were.
            for obj in context.selected_objects:
                obj.select_set(False)

            for obj in original_selection:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)

            if (
                original_active is not None
                and original_active.name in bpy.data.objects
            ):
                context.view_layer.objects.active = original_active

        self.report(
            {'INFO'},
            f"Moved {len(original_selection)} origin(s) to mouse pointer"
        )
        return {'FINISHED'}


class VIEW3D_PT_origin_to_mouse_pointer(bpy.types.Panel):
    bl_label = "Origin to Mouse Pointer"
    bl_idname = "VIEW3D_PT_origin_to_mouse_pointer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Object Mode shortcut: U")
        col.label(text="Uses the mouse pointer position")

        col.separator()

        col.operator(
            OBJECT_OT_origin_to_mouse_pointer.bl_idname,
            text="Origin to Mouse Pointer",
            icon='PIVOT_CURSOR',
        )


classes = (
    OBJECT_OT_origin_to_mouse_pointer,
    VIEW3D_PT_origin_to_mouse_pointer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    keyconfig = bpy.context.window_manager.keyconfigs.addon

    if keyconfig:
        # Object Mode keymap means U does not replace UV unwrap in Edit Mode.
        keymap = keyconfig.keymaps.new(
            name='Object Mode',
            space_type='EMPTY',
        )

        keymap_item = keymap.keymap_items.new(
            OBJECT_OT_origin_to_mouse_pointer.bl_idname,
            type='U',
            value='PRESS',
        )

        addon_keymaps.append((keymap, keymap_item))


def unregister():
    for keymap, keymap_item in addon_keymaps:
        keymap.keymap_items.remove(keymap_item)

    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
