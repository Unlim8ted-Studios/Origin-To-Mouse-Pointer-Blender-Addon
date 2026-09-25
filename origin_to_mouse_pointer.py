bl_info = {
    "name": "Origin to Mouse Pointer",
    "author": "Unlim8ted Studios",
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Object Mode",
    "description": "Set selected object origins to the 3D point under the mouse pointer",
    "category": "Object",
}

import bpy
import rna_keymap_ui

from bpy_extras import view3d_utils


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

OPERATOR_IDNAME = "object.origin_to_mouse_pointer"
KEYMAP_NAME = "Object Mode"

DEFAULT_KEY = 'U'

ADDON_ID = __package__ if __package__ else __name__


# Keep references to keymap items created by this add-on so they
# can be removed cleanly when the add-on is disabled.
addon_keymaps = []


# ------------------------------------------------------------
# Keymap helpers
# ------------------------------------------------------------

def keymap_item_matches_plain_u(kmi):
    """
    Return True if the keymap item uses plain U with no modifiers.
    """

    return (
        kmi.type == 'U'
        and kmi.value == 'PRESS'
        and not kmi.ctrl
        and not kmi.shift
        and not kmi.alt
        and not kmi.oskey
        and getattr(kmi, "key_modifier", 'NONE') == 'NONE'
        and kmi.active
    )


def find_plain_u_conflict(context=None):
    """
    Look for another active Object Mode command already using plain U.

    Returns:
        (keymap_item, keyconfig_name)

    or:

        (None, None)
    """

    if context is None:
        context = bpy.context

    wm = context.window_manager

    if wm is None:
        return None, None

    # Check the user's effective keymap first, then Blender's default.
    #
    # We deliberately do not check the add-on keyconfig here because
    # that could include our own shortcut.
    keyconfigs_to_check = []

    if wm.keyconfigs.user is not None:
        keyconfigs_to_check.append(
            ("User", wm.keyconfigs.user)
        )

    if wm.keyconfigs.default is not None:
        keyconfigs_to_check.append(
            ("Blender", wm.keyconfigs.default)
        )

    checked_items = set()

    for config_name, keyconfig in keyconfigs_to_check:
        keymap = keyconfig.keymaps.get(KEYMAP_NAME)

        if keymap is None:
            continue

        for kmi in keymap.keymap_items:
            # Ignore our own operator.
            if kmi.idname == OPERATOR_IDNAME:
                continue

            # Avoid reporting the same logical item twice if Blender
            # exposes it through multiple keyconfigs.
            signature = (
                kmi.idname,
                kmi.type,
                kmi.value,
                kmi.ctrl,
                kmi.shift,
                kmi.alt,
                kmi.oskey,
            )

            if signature in checked_items:
                continue

            checked_items.add(signature)

            if keymap_item_matches_plain_u(kmi):
                return kmi, config_name

    return None, None


def get_addon_keymap_item():
    """
    Return this add-on's keymap and keymap item from the add-on
    key configuration.
    """

    wm = bpy.context.window_manager

    if wm is None:
        return None, None

    keyconfig = wm.keyconfigs.addon

    if keyconfig is None:
        return None, None

    keymap = keyconfig.keymaps.get(KEYMAP_NAME)

    if keymap is None:
        return None, None

    for kmi in keymap.keymap_items:
        if kmi.idname == OPERATOR_IDNAME:
            return keymap, kmi

    return None, None


def get_user_keymap_item(context):
    """
    Find the user-editable version of this add-on's shortcut.

    Blender exposes add-on shortcuts in the user key configuration
    so they can be edited and saved normally.
    """

    wm = context.window_manager

    if wm is None:
        return None, None, None

    keyconfig = wm.keyconfigs.user

    if keyconfig is None:
        return None, None, None

    keymap = keyconfig.keymaps.get(KEYMAP_NAME)

    if keymap is None:
        return None, None, None

    for kmi in keymap.keymap_items:
        if kmi.idname == OPERATOR_IDNAME:
            return keyconfig, keymap, kmi

    return None, None, None


def register_keymap():
    """
    Register U as the default shortcut.

    If plain U is already used by another Object Mode action,
    register the shortcut but leave it disabled.
    """

    wm = bpy.context.window_manager

    if wm is None:
        return

    keyconfig = wm.keyconfigs.addon

    if keyconfig is None:
        return

    keymap = keyconfig.keymaps.new(
        name=KEYMAP_NAME,
        space_type='EMPTY',
    )

    keymap_item = keymap.keymap_items.new(
        OPERATOR_IDNAME,
        type=DEFAULT_KEY,
        value='PRESS',
    )

    conflict, _ = find_plain_u_conflict()

    # If U is already being used, keep our shortcut present so the
    # user can edit it, but don't activate it automatically.
    if conflict is not None:
        keymap_item.active = False

    addon_keymaps.append(
        (
            keymap,
            keymap_item,
        )
    )


def unregister_keymap():
    """
    Remove only the keymap items created by this add-on.
    """

    for keymap, keymap_item in addon_keymaps:
        try:
            keymap.keymap_items.remove(
                keymap_item
            )
        except (
            ReferenceError,
            RuntimeError,
        ):
            pass

    addon_keymaps.clear()


# ------------------------------------------------------------
# Mouse world-position calculation
# ------------------------------------------------------------

def get_mouse_world_position(context, event):
    """
    Return a world-space point corresponding to the mouse pointer.
    """

    region = context.region
    rv3d = context.region_data

    if region is None or rv3d is None:
        return None

    mouse = (
        event.mouse_region_x,
        event.mouse_region_y,
    )

    # Create a ray passing through the mouse pointer.
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

    depsgraph = context.evaluated_depsgraph_get()

    hit, location, normal, face_index, hit_object, matrix = (
        context.scene.ray_cast(
            depsgraph,
            ray_origin,
            ray_direction,
        )
    )

    # If the mouse is over actual geometry, use the surface point.
    if hit:
        return location.copy()

    # Empty space has no unique 3D position, so use the active
    # object's depth as the reference plane.
    active = context.view_layer.objects.active

    if active is not None:
        depth_reference = (
            active.matrix_world.translation.copy()
        )
    else:
        depth_reference = (
            context.scene.cursor.location.copy()
        )

    return view3d_utils.region_2d_to_location_3d(
        region,
        rv3d,
        mouse,
        depth_reference,
    )


# ------------------------------------------------------------
# Operator
# ------------------------------------------------------------

class OBJECT_OT_origin_to_mouse_pointer(
    bpy.types.Operator
):
    """
    Set selected object origins to the point under the mouse pointer.
    """

    bl_idname = OPERATOR_IDNAME
    bl_label = "Origin to Mouse Pointer"
    bl_options = {
        'REGISTER',
        'UNDO',
    }

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == 'VIEW_3D'
            and context.mode == 'OBJECT'
            and len(context.selected_objects) > 0
        )

    def invoke(self, context, event):
        target = get_mouse_world_position(
            context,
            event,
        )

        if target is None:
            self.report(
                {'ERROR'},
                "Could not determine a 3D mouse position",
            )

            return {'CANCELLED'}

        scene = context.scene

        original_cursor = (
            scene.cursor.location.copy()
        )

        original_active = (
            context.view_layer.objects.active
        )

        original_selection = list(
            context.selected_objects
        )

        try:
            # Blender's origin_set operator can move origins to the
            # 3D Cursor. Temporarily move the cursor to our calculated
            # point and restore it immediately afterward.
            scene.cursor.location = target

            bpy.ops.object.origin_set(
                type='ORIGIN_CURSOR',
                center='MEDIAN',
            )

        except RuntimeError as exc:
            self.report(
                {'ERROR'},
                f"Unable to set origin: {exc}",
            )

            return {'CANCELLED'}

        finally:
            # Restore the user's 3D Cursor.
            scene.cursor.location = (
                original_cursor
            )

            # Restore selection.
            for obj in list(context.selected_objects):
                obj.select_set(False)

            for obj in original_selection:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)

            # Restore active object.
            if (
                original_active is not None
                and original_active.name
                in bpy.data.objects
            ):
                context.view_layer.objects.active = (
                    original_active
                )

        self.report(
            {'INFO'},
            (
                f"Moved {len(original_selection)} "
                "origin(s) to mouse pointer"
            ),
        )

        return {'FINISHED'}


# ------------------------------------------------------------
# 3D View N-panel
# ------------------------------------------------------------

class VIEW3D_PT_origin_to_mouse_pointer(
    bpy.types.Panel
):
    bl_label = "Origin to Mouse Pointer"
    bl_idname = (
        "VIEW3D_PT_origin_to_mouse_pointer"
    )

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout

        col = layout.column(
            align=True
        )

        col.label(
            text="Set origin to mouse position"
        )

        col.separator()

        col.operator(
            OPERATOR_IDNAME,
            text="Origin to Mouse Pointer",
            icon='PIVOT_CURSOR',
        )


# ------------------------------------------------------------
# Add-on Preferences
# ------------------------------------------------------------

class ORIGINMOUSE_AddonPreferences(
    bpy.types.AddonPreferences
):
    bl_idname = ADDON_ID

    def draw(self, context):
        layout = self.layout

        layout.label(
            text="Keyboard Shortcut",
            icon='KEYINGSET',
        )

        layout.label(
            text="Default shortcut: U in Object Mode"
        )

        layout.separator()

        conflict, config_name = (
            find_plain_u_conflict(context)
        )

        keyconfig, keymap, keymap_item = (
            get_user_keymap_item(context)
        )

        # If Blender hasn't generated the user representation yet,
        # fall back to showing the add-on keymap item directly.
        if keymap_item is None:
            addon_keymap, addon_kmi = (
                get_addon_keymap_item()
            )

            wm = context.window_manager

            if (
                addon_keymap is not None
                and addon_kmi is not None
                and wm.keyconfigs.addon is not None
            ):
                keyconfig = (
                    wm.keyconfigs.addon
                )

                keymap = addon_keymap
                keymap_item = addon_kmi

        # ----------------------------------------------------
        # Conflict warning
        # ----------------------------------------------------

        if (
            conflict is not None
            and keymap_item is not None
            and keymap_item.type == 'U'
            and not keymap_item.ctrl
            and not keymap_item.shift
            and not keymap_item.alt
        ):
            warning = layout.box()

            warning.label(
                text="U is already in use.",
                icon='ERROR',
            )

            try:
                conflict_name = (
                    conflict.name
                    if conflict.name
                    else conflict.idname
                )
            except Exception:
                conflict_name = (
                    conflict.idname
                )

            warning.label(
                text=(
                    f"Used by: {conflict_name}"
                )
            )

            warning.label(
                text=(
                    "This add-on's shortcut was "
                    "left disabled."
                )
            )

            warning.label(
                text=(
                    "Choose another shortcut below "
                    "or enable it manually."
                )
            )

            if config_name:
                warning.label(
                    text=(
                        f"Conflict found in "
                        f"{config_name} keymap."
                    )
                )

            layout.separator()

        # ----------------------------------------------------
        # Native Blender keymap editor
        # ----------------------------------------------------

        if (
            keyconfig is not None
            and keymap is not None
            and keymap_item is not None
        ):
            layout.context_pointer_set(
                "keymap",
                keymap,
            )

            rna_keymap_ui.draw_kmi(
                [
                    "ADDON",
                    "USER",
                    "DEFAULT",
                ],
                keyconfig,
                keymap,
                keymap_item,
                layout,
                0,
            )

            layout.separator()

            info = layout.box()

            info.label(
                text=(
                    "This is Blender's normal "
                    "keymap control."
                ),
                icon='INFO',
            )

            info.label(
                text=(
                    "Changes here also appear in "
                    "Preferences > Keymap."
                )
            )

        else:
            box = layout.box()

            box.label(
                text=(
                    "Shortcut could not be displayed."
                ),
                icon='ERROR',
            )

            box.label(
                text=(
                    "You can edit it in "
                    "Preferences > Keymap."
                )
            )


# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------

classes = (
    OBJECT_OT_origin_to_mouse_pointer,
    VIEW3D_PT_origin_to_mouse_pointer,
    ORIGINMOUSE_AddonPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    register_keymap()


def unregister():
    unregister_keymap()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
