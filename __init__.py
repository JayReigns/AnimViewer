bl_info = {
    "name": "Anim Viewer",
    "author": "JayReigns",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Tools > Animation",
    "description": "View and Assign all Actions",
    "category": "Animation"
}

import bpy
from bpy.props import IntProperty, FloatProperty, EnumProperty, StringProperty, BoolProperty, PointerProperty
from bpy.types import Operator, Menu, UIList, Panel, PropertyGroup, AddonPreferences


def get_global_props():
    return bpy.context.window_manager.animv_props

# cache selected object incase hidden after selection
def get_active_obj():
    if bpy.context.active_object:
        get_active_obj.obj = bpy.context.active_object
    
    try:
        return get_active_obj.obj
    except:
        return None


def update_animation(self, context):

    props = get_global_props()

    ob = get_active_obj()
    if not ob:
        return
    
    if ob.animation_data == None:
        ob.animation_data_create()
    
    # reset pose
    for n in ob.pose.bones:
        n.location = (0, 0, 0)
        n.rotation_quaternion = (1, 0, 0, 0)
        n.rotation_axis_angle = (0, 0, 1, 0)
        n.rotation_euler = (0, 0, 0)
        n.scale = (1, 1, 1)
        
    action = bpy.data.actions[ob.anim_list_index]
    ob.animation_data.action = action

    speed = props.speed
        
    scn = bpy.context.scene
    rnd = scn.render
    
    scn.use_preview_range = True
    scn.frame_preview_start = int(action.frame_range[0] / speed)
    scn.frame_preview_end = int(action.frame_range[1] / speed)

    scn.frame_current = scn.frame_preview_start
    
    rnd.frame_map_new = int(100 / speed)


#########################################################################################
# OPERATORS
#########################################################################################


class ANIMV_OT_SetSpeed(Operator):
    """Sets animation speed"""
    bl_idname = "animv.set_speed"
    bl_label = "Set Animation Speed"
    
    speed : FloatProperty(name="Animation Speed", default=1.0)
    
    @classmethod
    def poll(cls, context):
        ob = get_active_obj()
        return ob is not None \
            and ob.animation_data is not None \
            and ob.animation_data.action is not None \
    
    def execute(self, context):
        
        ob = get_active_obj()
        action = ob.animation_data.action

        speed = self.speed
        
        scn = bpy.context.scene
        rnd = scn.render
        
        scn.use_preview_range = True
        scn.frame_preview_start = int(action.frame_range[0] / speed)
        scn.frame_preview_end = int(action.frame_range[1] / speed)

        scn.frame_current = scn.frame_preview_start
        
        rnd.frame_map_new = int(100 / speed)
        
        return{'FINISHED'}


#########################################################################################
# PANELS
#########################################################################################


class ANIMV_UL_Action_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = True
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon="ACTION")
        elif self.layout_type in {'GRID'}:
            pass
        global filter_name2
        filter_name2 = self.filter_name


class ANIMV_PT_Viewer(Panel):
    bl_label = "Animation Viewer"
    bl_idname = "ANIMV_PT_Viewer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Animation"

    def draw(self, context):
        layout = self.layout
        
        ob = get_active_obj()
        if not ob:
            layout.label(text= "Select an Object/Armature", icon="POSE_HLT")
            return
        
        layout.label(text= ob.name, icon="POSE_HLT")
        
        row = layout.row(align=True)
        for s in (0.25, 0.5, 1, 1.25, 1.5, 2):
            row.operator(ANIMV_OT_SetSpeed.bl_idname, text=str(s)).speed = s
        
        layout.template_list("ANIMV_UL_Action_List", "", bpy.data, "actions", ob, "anim_list_index")


#########################################################################################
# PROPERTIES
#########################################################################################


class ANIMV_Props(PropertyGroup):

    speed: FloatProperty(
        name="Animation Speed",
        description="Set Animation Speed",
        update = update_animation,
        default=1.0,
    )


#########################################################################################
# REGISTER/UNREGISTER
#########################################################################################


classes = (
    ANIMV_OT_SetSpeed,
    ANIMV_UL_Action_List,
    ANIMV_PT_Viewer,
    ANIMV_Props,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Object.anim_list_index = IntProperty(
        update = update_animation, 
        description = "Anim Viewer's highlighted action on list for this object"
    )
    bpy.types.WindowManager.animv_props = PointerProperty(
        type=ANIMV_Props,
        name="ANIMV Props",
    )


def unregister():

    del bpy.types.Object.anim_list_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()